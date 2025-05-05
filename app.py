import re
from scripts.langfuse import LangfuseConnector
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from scripts.provider import GroqProvider, OpenAIProvider, OpenRouterProvider, GeminiProvider, EinfraProvider
from scripts.healthreact import HealthReact
from scripts.telegram import TelegramConnector
import os
from dotenv import load_dotenv
from langfuse.decorators import observe
import asyncio

class PromptEditorApp:
    def __init__(self, root):
        # Kontrola a případné vytvoření .env souboru
        env_path = os.path.join(os.path.dirname(__file__), '.env')
        required_keys = [
            'GROQ_API_KEY',
            'OPENAI_API_KEY',
            'OPENROUTER_API_KEY',
            'GEMINI_API_KEY',
            'EINFRA_API_KEY',
            'HR_API_KEY'
        ]
        if not os.path.exists(env_path):
            with open(env_path, 'w') as f:
                for key in required_keys:
                    f.write(f"{key}=PLACEHOLDER\n")
        load_dotenv(env_path)

        self.root = root
        self.root.title("Editor promptů")
        self.root.geometry("800x600")
        
        # Langfuse připojení
        self.langfuse = LangfuseConnector(
            public_api_key='pk-lf-1e3953fe-db0e-4cde-a7bc-9410fc82dedb',
            secret_api_key='sk-lf-acaf75c5-74af-4661-8660-825dd0e5ba92',
            api_url='https://cloud.langfuse.com',
            headers={'Content-Type': 'application/json'}
        )
        
        # API klíče (v produkci načítat z .env)
        self.api_keys = {
            'Groq': os.environ.get('GROQ_API_KEY', ''),
            'OpenAI': os.environ.get('OPENAI_API_KEY', ''),
            'OpenRouter': os.environ.get('OPENROUTER_API_KEY', ''),
            'Gemini': os.environ.get('GEMINI_API_KEY', ''),
            'Einfra': os.environ.get('EINFRA_API_KEY', '')
        }
        
        # Modely a provider
        self.provider_classes = {
            'Groq': GroqProvider,
            'OpenAI': OpenAIProvider,
            'OpenRouter': OpenRouterProvider,
            'Gemini': GeminiProvider,
            'Einfra': EinfraProvider
        }
        self.model_options = self._get_all_model_options()
        self.current_provider = None
        self.current_model = None
        
        self.prompt_data = None
        self.prompt_entries = []
        self.current_full_prompt_id = None
        
        # HealthReact instance
        self.healthreact = HealthReact(api_key=os.environ.get('HR_API_KEY'))
        # Regex pro možnosti datumu
        self.option_xx_regex = re.compile(r"^(\w+)_(" + "|".join(HealthReact.AGGREGATIONS) + r")_DAILY_(\d{2})$")
        self.today_regex = re.compile(r"^(\w+)_DAILY_TODAY$")
        self.generic_xx_regex_str = r"^(\w+)_(" + "|".join(HealthReact.AGGREGATIONS) + r")_DAILY_XX$"

        self.available_data_options = []
        self.data_select_var = tk.StringVar()
        self.data_select = None

        self.focused_text_widget = None
        
        # Telegram konektor
        self.telegram_connector = TelegramConnector()
        self.telegram_chat_id = tk.StringVar(value="7304423973")
        self.last_llm_result = None
        
        # Vytvoření UI
        self.create_widgets()
    
    # Získání všech dostupných modelů a providerů
    def _get_all_model_options(self):
        options = []
        for provider, cls in self.provider_classes.items():
            for model in getattr(cls, 'available_models', []):
                options.append(f"{provider}:{model}")
        return options
    
    # Widgety pro UI
    def create_widgets(self):
        top_frame = ttk.Frame(self.root, padding="10")
        top_frame.pack(fill=tk.X)

        
        ttk.Label(top_frame, text="Typ:").pack(side=tk.LEFT, padx=5)
        self.namespace_var = tk.StringVar(value="default")
        self.namespace_select = ttk.Combobox(top_frame, textvariable=self.namespace_var, 
                                             values=["default", "group", "user"], 
                                             width=10, state="readonly")
        self.namespace_select.pack(side=tk.LEFT, padx=5)
        self.namespace_select.bind("<<ComboboxSelected>>", self.on_namespace_change)

        # Combobox pro výběr uživatele (skrytý ve výchozím stavu)
        self.user_select_var = tk.StringVar()
        self.user_select = ttk.Combobox(top_frame, textvariable=self.user_select_var, state="readonly", width=25)
        self.user_select.pack_forget()
        self.user_select.bind("<<ComboboxSelected>>", self.on_user_selected)

        ttk.Label(top_frame, text="Uživatel:").pack(side=tk.LEFT, padx=5)
        self.prompt_name = ttk.Entry(top_frame, width=30)
        self.prompt_name.pack(side=tk.LEFT, padx=5)
        self.prompt_name.config(state="disabled")

        # Tlačítko Načíst
        self.load_prompt_btn = ttk.Button(top_frame, text="Načíst prompt", command=self.load_prompt)
        self.load_prompt_btn.pack(side=tk.LEFT, padx=5)
        
        #  Tlačítko pro načtení promptu
        self.editor_frame = ttk.Frame(self.root, padding="10")
        self.editor_frame.pack(fill=tk.BOTH, expand=True)
        
        # Scrolovací obraz
        self.canvas = tk.Canvas(self.editor_frame)
        scrollbar = ttk.Scrollbar(self.editor_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas_frame = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.canvas.bind('<Configure>', self.on_canvas_configure)
        
        bottom_frame = ttk.Frame(self.root, padding="10")
        bottom_frame.pack(fill=tk.X)
        
        ttk.Label(bottom_frame, text="Model:").pack(side=tk.LEFT, padx=5)
        self.model_var = tk.StringVar()
        self.model_select = ttk.Combobox(bottom_frame, textvariable=self.model_var, values=self.model_options, width=40, state="readonly")
        self.model_select.pack(side=tk.LEFT, padx=5)
        self.model_select.current(0)
        self.model_select.bind("<<ComboboxSelected>>", self.on_model_change)
        self.on_model_change()  # inicializace při startu
        
        # Tlačítka
        self.test_prompt_btn = ttk.Button(bottom_frame, text="Otestovat prompt", command=self.test_prompt)
        self.test_prompt_btn.pack(side=tk.RIGHT, padx=5)
        ttk.Button(bottom_frame, text="Uložit změny", command=self.save_changes).pack(side=tk.RIGHT, padx=5)
        
        # Tlačítko pro historii doporučení do samostatného frame pod ostatními tlačítky 
        self.history_frame = ttk.Frame(self.root, padding="0 0 10 10")
        self.history_button = ttk.Button(self.history_frame, text="Historie doporučení", command=self._show_history_for_selected_user)
        self.history_button.pack(side=tk.RIGHT, padx=5, pady=5)
        self.history_frame.pack(fill=tk.X, side=tk.BOTTOM, anchor="s")
        self._update_history_button_visibility()
        self._update_test_prompt_button_state()

    def _update_test_prompt_button_state(self):
        if hasattr(self, 'namespace_var') and self.namespace_var.get() == "default":
            self.test_prompt_btn.state(["disabled"])
        else:
            self.test_prompt_btn.state(["!disabled"])

    def _update_history_button_visibility(self):
        if hasattr(self, 'namespace_var') and self.namespace_var.get() == "user":
            self.history_frame.pack(fill=tk.X, side=tk.BOTTOM, anchor="s")
        else:
            self.history_frame.pack_forget()

    def on_namespace_change(self, event):
        namespace = self.namespace_var.get()
        if namespace == "user":
            self.prompt_name.pack_forget()
            self.user_select.pack(side=tk.LEFT, padx=5, before=self.load_prompt_btn)
            progress_dialog = tk.Toplevel(self.root)
            progress_dialog.title("Stahuji uživatele")
            progress_dialog.geometry("300x100")
            progress_dialog.transient(self.root)
            progress_dialog.grab_set()
            ttk.Label(progress_dialog, text="Stahuji uživatele...", padding=20).pack()
            progress_dialog.update()
            users = self.healthreact.get_user_available_data_names()
            progress_dialog.destroy()
            if not users:
                self.user_select['values'] = []
                self.user_select_var.set("")
                messagebox.showerror("Chyba", "Nebyli nalezeni žádní uživatelé.")
                return
            user_options = [f"{u['id']} - {u['name']}" for u in users]
            self.user_select['values'] = user_options
            self.user_id_map = {f"{u['id']} - {u['name']}": u['id'] for u in users}
            self.user_select_var.set(user_options[0])
            self.prompt_name.delete(0, tk.END)
            self.prompt_name.insert(0, users[0]['id'])
        else:
            self.user_select.pack_forget()
            self.prompt_name.pack(side=tk.LEFT, padx=5, before=self.load_prompt_btn)
            self.prompt_name.config(state="normal" if namespace != "default" else "disabled")
        self._update_history_button_visibility()
        self._update_test_prompt_button_state()

    def on_user_selected(self, event):
        selected = self.user_select_var.get()
        user_id = self.user_id_map.get(selected, "")
        self.prompt_name.delete(0, tk.END)
        self.prompt_name.insert(0, user_id)
    
    def on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_frame, width=event.width)
    
    def on_model_change(self, event=None):
        value = self.model_var.get() or self.model_options[0]
        provider, model = value.split(":", 1)
        api_key = self.api_keys.get(provider)
        provider_cls = self.provider_classes[provider]
        self.current_provider = provider_cls(api_key, model)
        self.current_model = model
    
    def load_prompt(self):
        try:
            namespace = self.namespace_var.get()
            if namespace == "default":
                full_prompt_id = "default"  
                self.prompt_name.config(state="normal")  
                self.prompt_name.delete(0, tk.END)
                self.prompt_name.insert(0, "default")
                self.prompt_name.config(state="disabled")  
                self.available_data_options = self.healthreact.get_available_data([], "default")
                print("DATA DEFAULT", self.available_data_options)
            else:
                if namespace == "user":
                    progress_dialog = tk.Toplevel(self.root)
                    progress_dialog.title("Načítám prompt")
                    progress_dialog.geometry("300x100")
                    progress_dialog.transient(self.root)
                    progress_dialog.grab_set()
                    ttk.Label(progress_dialog, text="Načítám prompt...", padding=20).pack()
                    progress_dialog.update()
                    selected = self.user_select_var.get()
                    prompt_id = self.user_id_map.get(selected, "")
                    user_record_types = []
                    for ulabel, uid in self.user_id_map.items():
                        if uid == prompt_id:
                            users = self.healthreact.get_user_available_data_names()
                            for u in users:
                                if u['id'] == prompt_id:
                                    user_record_types = u.get('recordTypes', [])
                                    break
                            break
                    self.available_data_options = self.healthreact.get_available_data(user_record_types, prompt_id) or []
                    print("DATA", self.available_data_options)
                else:
                    prompt_id = self.prompt_name.get()
                if not prompt_id:
                    messagebox.showerror("Chyba", "Zadejte název promptu")
                    return
                
                if namespace == "group":
                    full_prompt_id = f"group:{prompt_id}"
                    self.available_data_options = []
                elif namespace == "user":
                    full_prompt_id = f"user:{prompt_id}"
                else:
                    self.available_data_options = []
            
            self.current_full_prompt_id = full_prompt_id
            
            for widget in self.scrollable_frame.winfo_children():
                widget.destroy()
            self.prompt_entries = []
            self.focused_text_widget = None
            
            self.prompt_data = self.langfuse.get_prompt(full_prompt_id)
            prompt_list = self.prompt_data.get_langchain_prompt()
            prompt_list = [list(t) for t in prompt_list]

            for i, (role, content) in enumerate(prompt_list):
                frame = ttk.LabelFrame(self.scrollable_frame, text=f"Part {i+1} - Role: {role}")
                frame.pack(fill=tk.X, expand=True, pady=5, padx=5)
                
                text = tk.Text(frame, wrap=tk.WORD, height=10)
                text.pack(fill=tk.BOTH, expand=True, pady=5, padx=5)
                text.insert(tk.END, content)

                text.bind("<FocusIn>", self._on_text_focus)
                
                self.prompt_entries.append((role, text))
            
            if self.available_data_options:
                data_frame = ttk.LabelFrame(self.scrollable_frame, text="Dostupná data pro uživatele")
                data_frame.pack(fill=tk.X, expand=True, pady=5, padx=5)
                self.data_select_var.set(self.available_data_options[0])
                self.data_select = ttk.Combobox(data_frame, textvariable=self.data_select_var, values=self.available_data_options, state="readonly")
                self.data_select.pack(side=tk.LEFT, fill=tk.X, padx=5, pady=5, expand=True)
                
                insert_btn = ttk.Button(data_frame, text="Vložit", command=self.insert_selected_data)
                insert_btn.pack(side=tk.LEFT, padx=5)
            
            if namespace == "user":
                progress_dialog.destroy()
            
        except Exception as e:
            messagebox.showerror("Chyba", f"Nepodařilo se načíst prompt: {str(e)}")
    
    def _on_text_focus(self, event):
        self.focused_text_widget = event.widget

    def insert_selected_data(self):
        if self.focused_text_widget is not None:
            value = self.data_select_var.get()
            if value:
                to_insert = f"{{{value}}}"
                try:
                    self.focused_text_widget.insert(tk.INSERT, to_insert)
                except Exception as e:
                    messagebox.showerror("Chyba", f"Chyba při vkládání: {str(e)}")
        else:
            messagebox.showwarning("Pozor", "Nejprve klikněte do pole, kam chcete data vložit.")
    
    def _extract_bracketed_vars(self, text):
        import re
        return re.findall(r'\{([^{}]+)\}', text)

    def _validate_prompt_vars(self, updated_prompt):
        allowed_types = set(HealthReact.DATA_TYPES)
        allowed_aggregations = set(HealthReact.AGGREGATIONS)

        current_allowed_patterns = set()
        is_user_context = bool(self.available_data_options) 

        if is_user_context:
            for opt in self.available_data_options:
                if "_DAILY_XX" in opt:
                    pattern_str = opt.replace("_DAILY_XX", "_DAILY_(\\d{2})")
                    current_allowed_patterns.add(re.compile(f"^{pattern_str}$"))
                elif "_DAILY_TODAY" in opt:
                    current_allowed_patterns.add(opt)
                if "_DAILY_XX" in opt:
                    current_allowed_patterns.add(opt)

        else:
            for data_type in allowed_types:
                for agg in allowed_aggregations:
                    current_allowed_patterns.add(re.compile(f"^{data_type}_{agg}_DAILY_(\\d{{2}})$"))
                current_allowed_patterns.add(f"{data_type}_DAILY_TODAY")

        for i, (role, content) in enumerate(updated_prompt):
            for var in self._extract_bracketed_vars(content):
                is_valid = False
                validation_error = None

                for pattern in current_allowed_patterns:
                    if isinstance(pattern, str) and pattern == var:
                        is_valid = True
                        if is_user_context and "_DAILY_XX" in var:
                            is_valid = False
                            validation_error = f"Proměnná '{var}' obsahuje XX. Nahraďte XX dvouciferným číslem (01-99)."
                        break
                    elif hasattr(pattern, 'match'):
                        match = pattern.match(var)
                        if match:
                            if len(match.groups()) > 0:
                                days_str = match.groups()[-1]
                                try:
                                    days = int(days_str)
                                    if 1 <= days <= 99:
                                        is_valid = True
                                        break
                                    else:
                                        validation_error = f"Počet dní (XX) v '{var}' musí být mezi 01 a 99 (nalezeno: {days_str})."
                                        is_valid = False
                                        break
                                except ValueError:
                                    validation_error = f"Neplatný formát čísla dní v '{var}'."
                                    is_valid = False
                                    break
                            else:
                                is_valid = True
                                break

                if not is_valid:
                    final_error = validation_error or f"Proměnná '{var}' není povolena nebo má neplatný formát."
                    if not is_user_context:
                        match_xx = self.option_xx_regex.match(var)
                        match_today = self.today_regex.match(var)
                        if not match_xx and not match_today:
                            final_error = f"Neznámý formát proměnné: '{var}'. Očekáváno TYPE_AGGREGATION_DAILY_XX nebo TYPE_DAILY_TODAY."
                        elif match_xx:
                            dtype, agg, dstr = match_xx.groups()
                            if dtype not in allowed_types:
                                final_error = f"Neznámý datový typ '{dtype}' v '{var}'."
                            elif agg not in allowed_aggregations:
                                final_error = f"Neznámá agregace '{agg}' v '{var}'."
                            elif not (1 <= int(dstr) <= 99):
                                final_error = f"Počet dní (XX) v '{var}' musí být mezi 01 a 99."
                        elif match_today:
                            dtype = match_today.group(1)
                            if dtype not in allowed_types:
                                final_error = f"Neznámý datový typ '{dtype}' v '{var}'."

                    return False, var, final_error

        return True, None, None

    def save_changes(self):
        try:
            if not self.prompt_entries:
                messagebox.showerror("Chyba", "Není načten žádný prompt k uložení")
                return
            
            updated_prompt = []
            for i, (role, text_widget) in enumerate(self.prompt_entries):
                content = text_widget.get("1.0", tk.END).strip()
                updated_prompt.append((role, content))
            
            valid, unknown_var, error_reason = self._validate_prompt_vars(updated_prompt)
            if not valid:
                messagebox.showerror("Chyba validace", f"Chyba v proměnné: {{{unknown_var}}}\n{error_reason}")
                return
            
            print("\n===== DEBUG INFO: PROMPT UPDATE =====")
            print(f"Prompt Identifier: {self.current_full_prompt_id}")
            print("\nPrompt Content:")
            for i, (role, content) in enumerate(updated_prompt):
                print(f"\nPart {i+1}:")
                print(f"Role: {role}")
                print(f"Content: {content}")
                print("-" * 40)
            
            print("\nSending to update_prompt function...")
            response = self.langfuse.update_prompt(self.current_full_prompt_id, updated_prompt)
            print(f"Response from update_prompt: {response}")
            
            messagebox.showinfo("Úspěch", "Prompt byl úspěšně uložen")
        except Exception as e:
            error_msg = f"Nepodařilo se uložit změny: {str(e)}"
            print(f"\nERROR: {error_msg}")
            messagebox.showerror("Chyba", error_msg)
    
    def test_prompt(self):
        """Test the current prompt with vybraný model a provider"""
        try:
            if not self.prompt_entries:
                messagebox.showerror("Chyba", "Není načten žádný prompt k otestování")
                return

            updated_prompt = []
            for i, (role, text_widget) in enumerate(self.prompt_entries):
                content = text_widget.get("1.0", tk.END).strip()
                updated_prompt.append((role, content))

            valid, unknown_var, error_reason = self._validate_prompt_vars(updated_prompt)
            if not valid:
                messagebox.showerror("Chyba validace", f"Chyba v proměnné: {{{unknown_var}}}\n{error_reason}")
                return

            namespace = self.namespace_var.get()
            user_id = None 
            if namespace == "user":
                selected = self.user_select_var.get()
                user_id = self.user_id_map.get(selected)  
                if not user_id:
                    messagebox.showerror("Chyba", "Nelze získat ID vybraného uživatele.")
                    return

            substituted_prompt = []
            var_values = {}
            for i, (role, content) in enumerate(updated_prompt):
                new_content = content
                vars_in_content = self._extract_bracketed_vars(content)
                for var in vars_in_content:
                    if user_id is not None:
                        if var not in var_values:
                            try:
                                value = self.healthreact.get_data_for_option(var, user_id)
                            except ValueError as e:
                                messagebox.showerror("Chyba dat", f"Chyba při získávání dat pro '{var}': {e}")
                                return
                            except Exception as e:
                                value = f"<chyba při načítání dat: {e}>"
                            var_values[var] = value
                        else:
                            value = var_values[var]

                        str_value = str(value)

                        escaped_value = str_value.replace('{', '{{').replace('}', '}}')
                        new_content = new_content.replace(f"{{{var}}}", escaped_value)
                    else:
                        pass

                substituted_prompt.append((role, new_content))

            progress_dialog = tk.Toplevel(self.root)
            progress_dialog.title("Testuji prompt")
            progress_dialog.geometry("300x100")
            progress_dialog.transient(self.root)
            progress_dialog.grab_set()

            ttk.Label(progress_dialog, text="Probíhá testování promptu přes LLM...", padding=20).pack()
            progress_dialog.update()

            try:
                if namespace == "user" and user_id:
                    response = self.current_provider.generate(self.langfuse, substituted_prompt, user_id=f"user:{user_id}")
                else:
                    response = self.current_provider.generate(self.langfuse, substituted_prompt)

                progress_dialog.destroy()
                result_dialog = tk.Toplevel(self.root)
                result_dialog.title("Výsledek testu promptu")
                result_dialog.geometry("800x600")
                result_dialog.transient(self.root)

                input_text = scrolledtext.ScrolledText(result_dialog, wrap=tk.WORD, height=15)
                input_text.pack(fill=tk.BOTH, expand=False, padx=10, pady=(10, 0))
                input_text.insert(tk.END, "Vstup do LLM:\n")
                for i, (role, content) in enumerate(substituted_prompt):
                    input_text.insert(tk.END, f"\nPart {i+1} (Role: {role}):\n{content}\n")
                if var_values:
                    input_text.insert(tk.END, "\nPoužitá data:\n")
                    for var, value in var_values.items():
                        input_text.insert(tk.END, f"{var}: {value}\n")
                else:
                    input_text.insert(tk.END, "(Žádná data nebyla nahrazena - pravděpodobně default/group prompt)\n")
                input_text.config(state=tk.DISABLED)

                # Výsledek
                ttk.Label(result_dialog, text="Výsledek od LLM:").pack(pady=(10, 0))
                result_text = scrolledtext.ScrolledText(result_dialog, wrap=tk.WORD, height=15)
                result_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
                result_text.insert(tk.END, response)
                result_text.config(state=tk.DISABLED)
                
                # Ulož výsledek pro odeslání do Telegramu
                self.last_llm_result = response
                
                # Telegram sekce v okně výsledku
                telegram_frame = ttk.Frame(result_dialog)
                telegram_frame.pack(pady=5)
                ttk.Label(telegram_frame, text="Telegram chat ID:").pack(side=tk.LEFT, padx=5)
                telegram_entry = ttk.Entry(telegram_frame, textvariable=self.telegram_chat_id, width=15)
                telegram_entry.pack(side=tk.LEFT, padx=5)
                send_btn = ttk.Button(telegram_frame, text="Odeslat do Telegramu", command=lambda: self.send_to_telegram_result(response))
                send_btn.pack(side=tk.LEFT, padx=5)

                ttk.Button(result_dialog, text="Zavřít", command=result_dialog.destroy).pack(pady=10)

            except Exception as e:
                progress_dialog.destroy()
                messagebox.showerror("Chyba", f"Chyba při generování odpovědi: {str(e)}")

        except Exception as e:
            messagebox.showerror("Chyba", f"Nepodařilo se otestovat prompt: {str(e)}")
    
    def send_to_telegram(self):
        try:
            chat_id = self.telegram_chat_id.get()
            text = getattr(self, 'last_llm_result', None)
            if not text:
                messagebox.showerror("Chyba", "Není žádný výsledek k odeslání.")
                return
            self.telegram_connector.send_message(chat_id, text)
            messagebox.showinfo("Telegram", "Zpráva byla odeslána do Telegramu.")
        except Exception as e:
            messagebox.showerror("Chyba", f"Nepodařilo se odeslat zprávu do Telegramu: {str(e)}")

    def send_to_telegram_result(self, text):
        try:
            chat_id = self.telegram_chat_id.get()
            if not text:
                messagebox.showerror("Chyba", "Není žádný výsledek k odeslání.")
                return
            self.telegram_connector.send_message(chat_id, text)
            messagebox.showinfo("Telegram", "Zpráva byla odeslána do Telegramu.")
        except Exception as e:
            messagebox.showerror("Chyba", f"Nepodařilo se odeslat zprávu do Telegramu: {str(e)}")

    def show_user_history(self, user_id: str, limit: int = 10):
        """
        Otevře nové okno a zobrazí historii doporučení (traces) pro daného uživatele.
        """
        import datetime
        traces = self.healthreact.get_user_traces(user_id, limit=limit)
        history_dialog = tk.Toplevel(self.root)
        history_dialog.title(f"Historie doporučení pro uživatele {user_id}")
        history_dialog.geometry("700x400")
        history_dialog.transient(self.root)
        tree = ttk.Treeview(history_dialog, columns=("Datum", "Výstup", "ID"), show="headings")
        tree.heading("Datum", text="Datum")
        tree.heading("Výstup", text="Výstup")
        tree.heading("ID", text="Trace ID")
        tree.column("Datum", width=180)
        tree.column("Výstup", width=400)
        tree.column("ID", width=120)
        tree.pack(fill=tk.BOTH, expand=True)
        for trace in traces:
            raw_date = getattr(trace, 'createdAt', '-')
            formatted_date = raw_date
            try:
                if raw_date and raw_date != '-':
                    dt = datetime.datetime.fromisoformat(raw_date.replace('Z', '+00:00'))
                    formatted_date = dt.strftime('%-d. %-m. %Y, %H:%M')
            except Exception:
                pass
            tree.insert("", tk.END, values=(formatted_date, getattr(trace, 'output', '-')[:100], getattr(trace, 'id', '-')))
        def on_select(event):
            selected = tree.focus()
            if not selected:
                return
            values = tree.item(selected, 'values')
            trace_id = values[2]
            trace = next((t for t in traces if getattr(t, 'id', None) == trace_id), None)
            if trace:
                self.show_trace_detail(trace)
        tree.bind("<Double-1>", on_select)
        ttk.Label(history_dialog, text="Dvojklikem na řádek zobrazíte detail doporučení.").pack(pady=5)

    def show_trace_detail(self, trace):
        """
        Zobrazí detailní informace o konkrétním trace v novém okně.
        """
        detail_dialog = tk.Toplevel(self.root)
        detail_dialog.title(f"Detail doporučení {getattr(trace, 'id', '-')}")
        detail_dialog.geometry("600x400")
        detail_dialog.transient(self.root)
        
        text = scrolledtext.ScrolledText(detail_dialog, wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True)
        text.insert(tk.END, f"Trace ID: {getattr(trace, 'id', '-')}")
        text.insert(tk.END, f"\nName: {getattr(trace, 'name', '-')}")
        text.insert(tk.END, f"\nInput: {getattr(trace, 'input', '-')}")
        text.insert(tk.END, f"\nOutput: {getattr(trace, 'output', '-')}")
        text.insert(tk.END, f"\nTags: {getattr(trace, 'tags', '-')}")
        text.insert(tk.END, f"\nMetadata: {getattr(trace, 'metadata', '-')}")
        text.insert(tk.END, f"\nVytvořeno: {getattr(trace, 'createdAt', '-')}")
        text.config(state=tk.DISABLED)
        ttk.Button(detail_dialog, text="Zavřít", command=detail_dialog.destroy).pack(pady=10)

    def _show_history_for_selected_user(self):
        namespace = self.namespace_var.get()
        if namespace == "user":
            selected = self.user_select_var.get()
            user_id = self.user_id_map.get(selected)
            if user_id:
                self.show_user_history(user_id)
            else:
                messagebox.showerror("Chyba", "Není vybrán žádný uživatel.")
        else:
            messagebox.showinfo("Info", "Historie doporučení je dostupná pouze pro uživatelský kontext.")

@observe()
def main():
    root = tk.Tk()
    app = PromptEditorApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()