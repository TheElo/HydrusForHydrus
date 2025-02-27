import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import sqlite3
import hydrus_api
from tqdm import tqdm
import json
import os
import pyperclip

# Constants
API_URL = "APIURL"
ACCESS_KEY = "YOUR API KEY"
POPULATE_DB_WITH_EXAMPLES = True
WHITELIST = ["system:inbox", "system:filetype is animation, image, video"]
BLACKLIST = ["gore"]
TABNAME = "HFH"
LIMIT = 2048
DEFAULT_SCORE = 0.1
DEFAULT_SCORE_INCREMENT = 0.1

# Initialize Database
def initialize_database():
    mydb = sqlite3.connect('db.db')
    cmydb = mydb.cursor()
    cmydb.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='TagScores'")
    table_exists = cmydb.fetchone()
    if not table_exists:
        cmydb.execute("""
            CREATE TABLE TagScores (
                tag TEXT,
                score REAL,
                siblings TEXT,
                comment TEXT
            )
        """)
    cmydb.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Settings'")
    settings_table_exists = cmydb.fetchone()
    if not settings_table_exists:
        cmydb.execute("""
            CREATE TABLE Settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        # Initialize settings with default values
        default_settings = [
            ('API_URL', API_URL),
            ('ACCESS_KEY', ACCESS_KEY),
            ('TABNAME', TABNAME),
            ('LIMIT', str(LIMIT)),
            ('DEFAULT_SCORE', str(DEFAULT_SCORE)),
            ('SCORE_INCREMENT', str(DEFAULT_SCORE_INCREMENT)),
            ('WINDOW_SIZE', '800x600'),
            ('WINDOW_POSITION', '+100+100'),
            ('COLUMN_WIDTHS', json.dumps({"Tag": 150, "Score": 100, "Siblings": 150, "Comment": 200})),
            ('SELECTED_TAB', 'Data'),
            ('FONT_SIZE', '14'),
            ('ENTRY_WIDTH', '40'),
            ('EXAMPLES_POPULATED', 'False')  # Add a flag to indicate if examples have been populated
        ]
        cmydb.executemany("INSERT INTO Settings (key, value) VALUES (?, ?)", default_settings)
    mydb.commit()
    mydb.close()

# Populate Database with Examples
def example_population():
    mydb = sqlite3.connect('db.db')
    cmydb = mydb.cursor()
    example_data = [
        ('samus aran', 0.3, None, None),
        ('elf', 0.2, None, "give positive score to things you like"),
        ('blood', -1.0, None, 'go negative for things you dont like, think how much good stuff it would need to balance it, go high for really bad stuff'),
        ('system:has audio', 0.1, None, None),
        ('system:ratio = 16:9', 0.1, None, 'I like files that fit my screen well'),
        ('science fiction', 0.2, None, '*spaceship noises*'),
        ('computer', 0.1, None, 'computer for the win!'),
        ('monochrome', -0.1, None, 'Why does it burn when I see?'),
        ('greyscale', -0.1, None, 'Why does it burn when I see?'),
        ('system:has transparency', -0.1, None, 'transparency can be annoying'),
        ('system:width = 3,840', 0.1, None, 'prefer 4k files'),
        ('system:height = 2,160', 0.1, None, 'prefer 4k files')
    ]
    # Check if example data already exists
    cmydb.execute('SELECT tag FROM TagScores')
    existing_tags = {row[0] for row in cmydb.fetchall()}
    new_data = [data for data in example_data if data[0] not in existing_tags]
    if new_data:
        cmydb.executemany("""
            INSERT INTO TagScores (tag, score, siblings, comment) VALUES (?, ?, ?, ?)
        """, new_data)
        mydb.commit()
    mydb.close()

# Load Database Contents
def load_database_contents():
    mydb = sqlite3.connect('db.db')
    cmydb = mydb.cursor()
    cmydb.execute('SELECT * FROM TagScores')
    rows = cmydb.fetchall()
    mydb.close()
    return rows

# Save Database Changes
def save_database_changes(rows):
    mydb = sqlite3.connect('db.db')
    cmydb = mydb.cursor()
    cmydb.execute('DELETE FROM TagScores')
    cmydb.executemany("""
        INSERT INTO TagScores (tag, score, siblings, comment) VALUES (?, ?, ?, ?)
    """, rows)
    mydb.commit()
    mydb.close()

# Save Settings to Database
def save_settings_to_db(api_url, access_key, tabname, limit, default_score, score_increment, window_size, window_position, column_widths, selected_tab, font_size, entry_width, examples_populated):
    mydb = sqlite3.connect('db.db')
    cmydb = mydb.cursor()
    settings = [
        ('API_URL', api_url),
        ('ACCESS_KEY', access_key),
        ('TABNAME', tabname),
        ('LIMIT', str(limit)),
        ('DEFAULT_SCORE', str(default_score)),
        ('SCORE_INCREMENT', str(score_increment)),
        ('WINDOW_SIZE', window_size),
        ('WINDOW_POSITION', window_position),
        ('COLUMN_WIDTHS', json.dumps(column_widths)),
        ('SELECTED_TAB', selected_tab),
        ('FONT_SIZE', str(font_size)),
        ('ENTRY_WIDTH', str(entry_width)),
        ('EXAMPLES_POPULATED', examples_populated)  # Update the flag
    ]
    for key, value in settings:
        cmydb.execute("REPLACE INTO Settings (key, value) VALUES (?, ?)", (key, value))
    mydb.commit()
    mydb.close()

# Load Settings from Database
def load_settings_from_db():
    mydb = sqlite3.connect('db.db')
    cmydb = mydb.cursor()
    cmydb.execute('SELECT key, value FROM Settings')
    settings = {row[0]: row[1] for row in cmydb.fetchall()}
    mydb.close()
    return settings

# DB High Score Archiver
def db_high_score_archiver(client, blacklist, whitelist, limit, tabname):
    def find_page_key(tabs, tabname):
        if 'pages' in tabs and isinstance(tabs['pages'], list):
            for page in tabs['pages']:
                if page.get('name') == tabname:
                    return page.get('page_key')
                if 'pages' in page and isinstance(page['pages'], list):
                    sub_page_key = find_page_key(page, tabname)
                    if sub_page_key:
                        return sub_page_key
        return None

    def display_error(title, message):
        messagebox.showerror(title, message)

    try:
        ScoreAndIDs = {}
        pbar = tqdm(total=len(load_database_contents()), desc="Processing DB Tags", miniters=10, ncols=80)
        if blacklist:
            for tag in blacklist:
                blacklist[blacklist.index(tag)] = "-" + tag
        tag_list = blacklist + whitelist
        for row in load_database_contents():
            tag, score, _, _ = row
            if score is None:
                score = DEFAULT_SCORE
            query = [tag] + tag_list
            file_ids = client.search_files(query, file_sort_type=13)
            for file_id in file_ids:
                if file_id not in ScoreAndIDs:
                    ScoreAndIDs[file_id] = score
                else:
                    ScoreAndIDs[file_id] += score
            pbar.update(1)
        pbar.close()

        sorted_file_ids = sorted(ScoreAndIDs.items(), key=lambda x: x[1], reverse=True)
        top_file_ids = [file_id for file_id, score in sorted_file_ids[:limit]]

        page_key = find_page_key(client.get_pages(), tabname)
        if not page_key:
            display_error("Error", f"Tab '{tabname}' not found.")
            return

        client.add_files_to_page(page_key, top_file_ids)
        messagebox.showinfo("Success", f"Files added to tab '{tabname}'.")
    except Exception as e:
        display_error("Error", str(e))

# Main Application
class HydrusFileHighScoreApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.settings = load_settings_from_db()
        self.title("Hydrus File High Score Archiver")
        self.geometry(self.settings.get("WINDOW_SIZE", "800x600"))
        self.geometry(self.settings.get("WINDOW_POSITION", "+100+100"))

        # Dark Mode Theme
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure('.', background="#2b2b2b", foreground="#ffffff", selectbackground="#4c4c4c", selectforeground="#ffffff")
        self.style.map('.', background=[('active', '#555555')])

        # Define custom styles for buttons
        self.style.configure('TButtonGreen.TButton', background="#4CAF50", foreground="#ffffff", font=('Helvetica', int(self.settings.get("FONT_SIZE", 10))))
        self.style.map('TButtonGreen.TButton', background=[('active', '#45a049')])
        self.style.configure('TButtonRed.TButton', background="#F44336", foreground="#ffffff", font=('Helvetica', int(self.settings.get("FONT_SIZE", 10))))
        self.style.map('TButtonRed.TButton', background=[('active', '#d32f2f')])
        self.style.configure('TButtonBlue.TButton', background="#2196F3", foreground="#ffffff", font=('Helvetica', int(self.settings.get("FONT_SIZE", 10))))
        self.style.map('TButtonBlue.TButton', background=[('active', '#1976d2')])

        # Custom style for dark entry background
        self.style.configure('Dark.TEntry', background="#2b2b2b", foreground="#ffffff", fieldbackground="#2b2b2b", font=('Helvetica', int(self.settings.get("FONT_SIZE", 10))), width=int(self.settings.get("ENTRY_WIDTH", 40)))

        # Custom style for treeview
        self.style.configure('Treeview', background="#2b2b2b", foreground="#ffffff", fieldbackground="#2b2b2b", font=('Helvetica', int(self.settings.get("FONT_SIZE", 10))))
        self.style.configure('Treeview.Heading', background="#2b2b2b", foreground="#ffffff", font=('Helvetica', int(self.settings.get("FONT_SIZE", 10))))

        # Notebook for tabs
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(expand=1, fill='both')

        # Data Tab
        self.data_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.data_tab, text="Data")

        # Treeview in Data Tab
        self.tree = ttk.Treeview(self.data_tab, columns=("Tag", "Score", "Siblings", "Comment"), show='headings')
        self.tree.heading("Tag", text="Tag", command=lambda: self.sort_column("Tag"))
        self.tree.heading("Score", text="Score", command=lambda: self.sort_column("Score"))
        self.tree.heading("Siblings", text="Siblings", command=lambda: self.sort_column("Siblings"))
        self.tree.heading("Comment", text="Comment", command=lambda: self.sort_column("Comment"))
        column_widths = json.loads(self.settings.get("COLUMN_WIDTHS", json.dumps({"Tag": 150, "Score": 100, "Siblings": 150, "Comment": 200})))
        for col in column_widths:
            self.tree.column(col, width=int(column_widths[col]))
        self.tree.pack(expand=1, fill='both')

        # Bind keyboard shortcuts
        self.tree.bind('<KeyPress-+>', self.increase_score)
        self.tree.bind('<KeyPress->', self.decrease_score)

        # Buttons in Data Tab
        self.add_button = ttk.Button(self.data_tab, text="Add", command=self.add_tag, style='TButtonGreen.TButton')
        self.add_button.pack(side='left', padx=5, pady=5)

        self.edit_button = ttk.Button(self.data_tab, text="Edit", command=self.edit_tag, style='TButtonBlue.TButton')
        self.edit_button.pack(side='left', padx=5, pady=5)

        self.delete_button = ttk.Button(self.data_tab, text="Delete", command=self.delete_tag, style='TButtonRed.TButton')
        self.delete_button.pack(side='left', padx=5, pady=5)

        self.execute_button = ttk.Button(self.data_tab, text="Execute", command=self.run_archiver, style='TButtonBlue.TButton')
        self.execute_button.pack(side='right', padx=5, pady=5)

        # Settings Tab
        self.settings_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.settings_tab, text="Settings")

        # Labels and Entries in Settings Tab
        self.api_url_label = ttk.Label(self.settings_tab, text="API URL:", font=('Helvetica', int(self.settings.get("FONT_SIZE", 10))))
        self.api_url_label.grid(row=0, column=0, padx=10, pady=5, sticky='w')
        self.api_url_entry = ttk.Entry(self.settings_tab, style='Dark.TEntry')
        self.api_url_entry.insert(0, self.settings.get("API_URL", API_URL))
        self.api_url_entry.grid(row=0, column=1, padx=10, pady=5)

        self.access_key_label = ttk.Label(self.settings_tab, text="Access Key:", font=('Helvetica', int(self.settings.get("FONT_SIZE", 10))))
        self.access_key_label.grid(row=1, column=0, padx=10, pady=5, sticky='w')
        self.access_key_entry = ttk.Entry(self.settings_tab, style='Dark.TEntry')
        self.access_key_entry.insert(0, self.settings.get("ACCESS_KEY", ACCESS_KEY))
        self.access_key_entry.grid(row=1, column=1, padx=10, pady=5)

        self.tab_name_label = ttk.Label(self.settings_tab, text="Tab Name:", font=('Helvetica', int(self.settings.get("FONT_SIZE", 10))))
        self.tab_name_label.grid(row=2, column=0, padx=10, pady=5, sticky='w')
        self.tab_name_entry = ttk.Entry(self.settings_tab, style='Dark.TEntry')
        self.tab_name_entry.insert(0, self.settings.get("TABNAME", TABNAME))
        self.tab_name_entry.grid(row=2, column=1, padx=10, pady=5)

        self.limit_label = ttk.Label(self.settings_tab, text="Limit:", font=('Helvetica', int(self.settings.get("FONT_SIZE", 10))))
        self.limit_label.grid(row=3, column=0, padx=10, pady=5, sticky='w')
        self.limit_entry = ttk.Entry(self.settings_tab, style='Dark.TEntry')
        self.limit_entry.insert(0, str(int(self.settings.get("LIMIT", LIMIT))))
        self.limit_entry.grid(row=3, column=1, padx=10, pady=5)

        self.default_score_label = ttk.Label(self.settings_tab, text="Default Score:", font=('Helvetica', int(self.settings.get("FONT_SIZE", 10))))
        self.default_score_label.grid(row=4, column=0, padx=10, pady=5, sticky='w')
        self.default_score_entry = ttk.Entry(self.settings_tab, style='Dark.TEntry')
        self.default_score_entry.insert(0, str(float(self.settings.get("DEFAULT_SCORE", DEFAULT_SCORE))))
        self.default_score_entry.grid(row=4, column=1, padx=10, pady=5)

        self.score_increment_label = ttk.Label(self.settings_tab, text="Score Increment:", font=('Helvetica', int(self.settings.get("FONT_SIZE", 10))))
        self.score_increment_label.grid(row=5, column=0, padx=10, pady=5, sticky='w')
        self.score_increment_entry = ttk.Entry(self.settings_tab, style='Dark.TEntry')
        self.score_increment_entry.insert(0, str(float(self.settings.get("SCORE_INCREMENT", DEFAULT_SCORE_INCREMENT))))
        self.score_increment_entry.grid(row=5, column=1, padx=10, pady=5)

        # Load initial data
        self.load_data()
        self.sort_column("Score", reverse=True)

    def load_data(self):
        rows = load_database_contents()
        for row in rows:
            self.tree.insert("", "end", values=row)
        self.set_initial_focus()

    def set_initial_focus(self):
        if self.tree.get_children():
            self.tree.selection_set(self.tree.get_children()[0])
            self.tree.focus(self.tree.get_children()[0])

    def add_tag(self):
        def on_ok():
            tag = tag_entry.get()
            score = score_entry.get()
            siblings = siblings_entry.get()
            comment = comment_entry.get()
            if tag and score:
                try:
                    score = float(score)
                    self.tree.insert("", "end", values=(tag, score, siblings, comment))
                    rows = load_database_contents()
                    rows.append((tag, score, siblings, comment))
                    save_database_changes(rows)
                    add_window.destroy()
                except ValueError:
                    messagebox.showerror("Error", "Score must be a number.")
            else:
                messagebox.showerror("Error", "Tag and Score are required fields.")

        def adjust_score(direction):
            try:
                current_score = float(score_entry.get())
                increment = float(self.settings.get("SCORE_INCREMENT", DEFAULT_SCORE_INCREMENT))
                new_score = current_score + direction * increment
                new_score = round(new_score, 2)  # Round to two decimal places
                score_entry.delete(0, tk.END)
                score_entry.insert(0, str(new_score))
            except ValueError:
                messagebox.showerror("Error", "Score must be a number.")

        # Check clipboard content
        clipboard_content = pyperclip.paste()
        if len(clipboard_content) < 80 and " " not in clipboard_content:
            initial_tag = clipboard_content
        else:
            initial_tag = ""

        add_window = tk.Toplevel(self)
        add_window.title("Add Tag")
        add_window.geometry("500x250")  # Adjusted width and height
        add_window.configure(bg="#2b2b2b")

        # Configure grid
        add_window.grid_columnconfigure(1, weight=1)

        tag_label = ttk.Label(add_window, text="Tag:", font=('Helvetica', int(self.settings.get("FONT_SIZE", 10))))
        tag_label.grid(row=0, column=0, padx=10, pady=5, sticky='w')
        tag_entry = ttk.Entry(add_window, style='Dark.TEntry')
        tag_entry.insert(0, initial_tag)
        tag_entry.grid(row=0, column=1, padx=10, pady=5, sticky='ew')
        tag_entry.focus_set()

        score_label = ttk.Label(add_window, text="Score:", font=('Helvetica', int(self.settings.get("FONT_SIZE", 10))))
        score_label.grid(row=1, column=0, padx=10, pady=5, sticky='w')
        score_entry = ttk.Entry(add_window, style='Dark.TEntry')
        score_entry.insert(0, str(float(self.settings.get("DEFAULT_SCORE", DEFAULT_SCORE))))  # Populate with default score
        score_entry.grid(row=1, column=1, padx=10, pady=5, sticky='ew')

        # Add "+" and "-" buttons next to the score entry
        plus_button = ttk.Button(add_window, text="+", command=lambda: adjust_score(1), style='TButtonGreen.TButton', width=2)
        plus_button.grid(row=1, column=2, padx=5, pady=5)
        minus_button = ttk.Button(add_window, text="-", command=lambda: adjust_score(-1), style='TButtonRed.TButton', width=2)
        minus_button.grid(row=1, column=3, padx=5, pady=5)

        siblings_label = ttk.Label(add_window, text="Siblings:", font=('Helvetica', int(self.settings.get("FONT_SIZE", 10))))
        siblings_label.grid(row=2, column=0, padx=10, pady=5, sticky='w')
        siblings_entry = ttk.Entry(add_window, style='Dark.TEntry')
        siblings_entry.grid(row=2, column=1, padx=10, pady=5, sticky='ew')

        comment_label = ttk.Label(add_window, text="Comment:", font=('Helvetica', int(self.settings.get("FONT_SIZE", 10))))
        comment_label.grid(row=3, column=0, padx=10, pady=5, sticky='w')
        comment_entry = ttk.Entry(add_window, style='Dark.TEntry')
        comment_entry.grid(row=3, column=1, padx=10, pady=5, sticky='ew')

        ok_button = ttk.Button(add_window, text="OK", command=on_ok, style='TButtonGreen.TButton')
        ok_button.grid(row=4, column=0, padx=10, pady=10)
        cancel_button = ttk.Button(add_window, text="Cancel", command=add_window.destroy, style='TButtonRed.TButton')
        cancel_button.grid(row=4, column=1, padx=10, pady=10)

        # Position the edit window over the parent window
        x = self.winfo_x() + self.winfo_width() // 2 - add_window.winfo_width() // 2
        y = self.winfo_y() + self.winfo_height() // 2 - add_window.winfo_height() // 2
        add_window.geometry(f"+{x}+{y}")

    def edit_tag(self):
        selected_item = self.tree.selection()
        if not selected_item:
            messagebox.showerror("Error", "Please select a tag to edit.")
            return
        item_values = self.tree.item(selected_item, "values")

        def on_ok():
            tag = tag_entry.get()
            score = score_entry.get()
            siblings = siblings_entry.get()
            comment = comment_entry.get()
            if tag and score:
                try:
                    score = float(score)
                    self.tree.item(selected_item, values=(tag, score, siblings, comment))
                    rows = load_database_contents()
                    rows = [row if row[0] != item_values[0] else (tag, score, siblings, comment) for row in rows]
                    save_database_changes(rows)
                    edit_window.destroy()
                except ValueError:
                    messagebox.showerror("Error", "Score must be a number.")
            else:
                messagebox.showerror("Error", "Tag and Score are required fields.")

        def adjust_score(direction):
            try:
                current_score = float(score_entry.get())
                increment = float(self.settings.get("SCORE_INCREMENT", DEFAULT_SCORE_INCREMENT))
                new_score = current_score + direction * increment
                new_score = round(new_score, 2)  # Round to two decimal places
                score_entry.delete(0, tk.END)
                score_entry.insert(0, str(new_score))
            except ValueError:
                messagebox.showerror("Error", "Score must be a number.")

        edit_window = tk.Toplevel(self)
        edit_window.title("Edit Tag")
        edit_window.geometry("500x250")  # Adjusted width and height
        edit_window.configure(bg="#2b2b2b")

        # Configure grid
        edit_window.grid_columnconfigure(1, weight=1)

        tag_label = ttk.Label(edit_window, text="Tag:", font=('Helvetica', int(self.settings.get("FONT_SIZE", 10))))
        tag_label.grid(row=0, column=0, padx=10, pady=5, sticky='w')
        tag_entry = ttk.Entry(edit_window, style='Dark.TEntry')
        tag_entry.insert(0, item_values[0])
        tag_entry.grid(row=0, column=1, padx=10, pady=5, sticky='ew')
        tag_entry.focus_set()

        score_label = ttk.Label(edit_window, text="Score:", font=('Helvetica', int(self.settings.get("FONT_SIZE", 10))))
        score_label.grid(row=1, column=0, padx=10, pady=5, sticky='w')
        score_entry = ttk.Entry(edit_window, style='Dark.TEntry')
        score_entry.insert(0, item_values[1])
        score_entry.grid(row=1, column=1, padx=10, pady=5, sticky='ew')

        # Add "+" and "-" buttons next to the score entry
        plus_button = ttk.Button(edit_window, text="+", command=lambda: adjust_score(1), style='TButtonGreen.TButton', width=2)
        plus_button.grid(row=1, column=2, padx=5, pady=5)
        minus_button = ttk.Button(edit_window, text="-", command=lambda: adjust_score(-1), style='TButtonRed.TButton', width=2)
        minus_button.grid(row=1, column=3, padx=5, pady=5)

        siblings_label = ttk.Label(edit_window, text="Siblings:", font=('Helvetica', int(self.settings.get("FONT_SIZE", 10))))
        siblings_label.grid(row=2, column=0, padx=10, pady=5, sticky='w')
        siblings_entry = ttk.Entry(edit_window, style='Dark.TEntry')
        siblings_entry.insert(0, item_values[2] if item_values[2] else "")
        siblings_entry.grid(row=2, column=1, padx=10, pady=5, sticky='ew')

        comment_label = ttk.Label(edit_window, text="Comment:", font=('Helvetica', int(self.settings.get("FONT_SIZE", 10))))
        comment_label.grid(row=3, column=0, padx=10, pady=5, sticky='w')
        comment_entry = ttk.Entry(edit_window, style='Dark.TEntry')
        comment_entry.insert(0, item_values[3] if item_values[3] else "")
        comment_entry.grid(row=3, column=1, padx=10, pady=5, sticky='ew')

        ok_button = ttk.Button(edit_window, text="OK", command=on_ok, style='TButtonGreen.TButton')
        ok_button.grid(row=4, column=0, padx=10, pady=10)
        cancel_button = ttk.Button(edit_window, text="Cancel", command=edit_window.destroy, style='TButtonRed.TButton')
        cancel_button.grid(row=4, column=1, padx=10, pady=10)

        # Position the edit window over the parent window
        x = self.winfo_x() + self.winfo_width() // 2 - edit_window.winfo_width() // 2
        y = self.winfo_y() + self.winfo_height() // 2 - edit_window.winfo_height() // 2
        edit_window.geometry(f"+{x}+{y}")

    def delete_tag(self):
        selected_item = self.tree.selection()
        if not selected_item:
            messagebox.showerror("Error", "Please select a tag to delete.")
            return
        item_values = self.tree.item(selected_item, "values")
        if messagebox.askyesno("Confirm", f"Are you sure you want to delete the tag '{item_values[0]}'?"):
            self.tree.delete(selected_item)
            rows = load_database_contents()
            rows = [row for row in rows if row[0] != item_values[0]]
            save_database_changes(rows)

    def run_archiver(self):
        api_url = self.api_url_entry.get()
        access_key = self.access_key_entry.get()
        tabname = self.tab_name_entry.get()
        limit = int(self.limit_entry.get())
        default_score = float(self.default_score_entry.get())
        client = hydrus_api.Client(access_key=access_key, api_url=api_url)
        db_high_score_archiver(client, BLACKLIST, WHITELIST, limit, tabname)

    def sort_column(self, col, reverse=False):
        l = [(self.tree.set(k, col), k) for k in self.tree.get_children('')]
        try:
            l.sort(key=lambda t: float(t[0]), reverse=reverse)
        except ValueError:
            l.sort(key=lambda t: t[0], reverse=reverse)
        for index, (val, k) in enumerate(l):
            self.tree.move(k, '', index)
        self.tree.heading(col, command=lambda: self.sort_column(col, not reverse))

    def increase_score(self, event):
        if event.char == '+':
            self.adjust_score(1)

    def decrease_score(self, event):
        if event.char == '-':
            self.adjust_score(-1)

    def adjust_score(self, direction):
        selected_item = self.tree.selection()
        if not selected_item:
            messagebox.showerror("Error", "Please select a tag to adjust.")
            return
        item_values = self.tree.item(selected_item, "values")
        try:
            score = float(item_values[1])
            increment = float(self.settings.get("SCORE_INCREMENT", DEFAULT_SCORE_INCREMENT))
            score += direction * increment
            score = round(score, 2)  # Round to two decimal places
            self.tree.item(selected_item, values=(item_values[0], score, item_values[2], item_values[3]))
            rows = load_database_contents()
            rows = [row if row[0] != item_values[0] else (item_values[0], score, item_values[2], item_values[3]) for row in rows]
            save_database_changes(rows)
        except ValueError:
            messagebox.showerror("Error", "Score must be a number.")

    def on_closing(self):
        # Save window size and position
        window_size = self.geometry().split('+')[0]
        window_position = f"+{self.winfo_x()}+{self.winfo_y()}"
        # Save column widths
        column_widths = {col: self.tree.column(col, "width") for col in self.tree["columns"]}
        # Save other settings
        save_settings_to_db(
            self.api_url_entry.get(),
            self.access_key_entry.get(),
            self.tab_name_entry.get(),
            int(self.limit_entry.get()),
            float(self.default_score_entry.get()),
            float(self.score_increment_entry.get()),
            window_size,
            window_position,
            column_widths,
            self.settings.get("SELECTED_TAB", "Data"),
            int(self.settings.get("FONT_SIZE", 14)),
            int(self.settings.get("ENTRY_WIDTH", 40)),
            self.settings.get("EXAMPLES_POPULATED", "False")  # Pass the flag
        )
        self.destroy()

# Run the Application
if __name__ == '__main__':
    initialize_database()
    examples_populated = load_settings_from_db().get("EXAMPLES_POPULATED", "False")
    if examples_populated == "False":
        example_population()
        save_settings_to_db(
            API_URL,
            ACCESS_KEY,
            TABNAME,
            LIMIT,
            DEFAULT_SCORE,
            DEFAULT_SCORE_INCREMENT,
            '800x600',
            '+100+100',
            {"Tag": 150, "Score": 100, "Siblings": 150, "Comment": 200},
            'Data',
            14,
            40,
            "True"  # Set the flag to True after population
        )
    app = HydrusFileHighScoreApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()