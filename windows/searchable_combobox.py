# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk

class SearchableCombobox(tk.Frame):
    """
    Un widget de combobox con funcionalidad de búsqueda.
    Implementado con un Listbox que se muestra usando .place() para evitar problemas con Toplevel y grab_set().
    """
    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        
        self.data = []
        self._var = tk.StringVar()
        self._callback = None  # Placeholder for the callback function
        
        self.entry = ttk.Entry(self, textvariable=self._var)
        self.entry.pack(fill="both", expand=True)

        self.entry.bind("<FocusIn>", self._on_focus_in)
        self.entry.bind("<FocusOut>", self._on_focus_out)
        self.entry.bind("<KeyRelease>", self._on_key_release)
        self._var.trace_add("write", self._on_var_change)
        
        self._listbox = None
        self._hide_job = None

    def set_callback(self, callback):
        """Sets a callback function to be called when the variable changes."""
        self._callback = callback

    def _on_var_change(self, name, index, mode):
        self.filter_listbox()
        if self._callback:
            self._callback()

    def _on_key_release(self, event):
        if event.keysym not in ("Up", "Down", "Return", "KP_Enter", "Escape", "Tab", "Shift_L", "Shift_R"):
            self.show_listbox()

        if not self._listbox:
            return

        if event.keysym == "Down":
            self._move_selection(1)
        elif event.keysym == "Up":
            self._move_selection(-1)
        elif event.keysym == "Return" or event.keysym == "KP_Enter":
            self._select_item_from_listbox()
        elif event.keysym == "Escape":
            self.hide_listbox()

    def _move_selection(self, delta):
        if not self._listbox: return
        current_selection = self._listbox.curselection()
        current_index = current_selection[0] if current_selection else -1
        new_index = current_index + delta
        
        if 0 <= new_index < self._listbox.size():
            self._listbox.selection_clear(0, tk.END)
            self._listbox.selection_set(new_index)
            self._listbox.see(new_index)
            self._listbox.activate(new_index)

    def _select_item_from_listbox(self, event=None):
        if self._listbox and self._listbox.curselection():
            value = self._listbox.get(self._listbox.curselection()[0])
            self.set(value)
            self.hide_listbox()
            self.entry.icursor(tk.END)
            self.entry.focus_set()

    def _on_focus_in(self, event):
        self._cancel_hide()
        self.show_listbox()

    def _on_focus_out(self, event):
        self._schedule_hide()
        
    def _schedule_hide(self):
        self._cancel_hide()
        self._hide_job = self.after(200, self.hide_listbox)
        
    def _cancel_hide(self):
        if self._hide_job:
            self.after_cancel(self._hide_job)
            self._hide_job = None

    def show_listbox(self):
        if self._listbox:
            return

        toplevel = self.winfo_toplevel()
        x = self.entry.winfo_rootx() - toplevel.winfo_rootx()
        y = self.entry.winfo_rooty() - toplevel.winfo_rooty() + self.entry.winfo_height()
        width = self.entry.winfo_width()
        
        self._listbox = tk.Listbox(toplevel, exportselection=False)
        self._listbox.place(x=x, y=y, width=width, height=150)
        
        self._listbox.bind("<ButtonRelease-1>", self._select_item_from_listbox)
        self._listbox.bind("<Enter>", lambda e: self._cancel_hide())
        self._listbox.bind("<Leave>", lambda e: self._schedule_hide())

        self.filter_listbox()

    def hide_listbox(self):
        if self._listbox:
            self._listbox.place_forget()
            self._listbox.destroy()
            self._listbox = None
    
    def set_data(self, data):
        self.data = sorted(data)
        self.filter_listbox()

    def filter_listbox(self):
        if not self._listbox:
            return

        search_term = self.entry.get().lower()
        
        current_selection = self._listbox.curselection()
        
        self._listbox.delete(0, tk.END)

        if not search_term:
            filtered_data = self.data
        else:
            filtered_data = [item for item in self.data if search_term in item.lower()]
        
        for item in filtered_data:
            self._listbox.insert(tk.END, item)
        
        if filtered_data:
            # Restaurar selección si es posible, o seleccionar el primero
            try:
                original_value = self._listbox.get(current_selection)
                if original_value in filtered_data:
                    new_index = filtered_data.index(original_value)
                    self._listbox.selection_set(new_index)
                    self._listbox.activate(new_index)
                else:
                    self._listbox.selection_set(0)
                    self._listbox.activate(0)
            except (tk.TclError, IndexError):
                 self._listbox.selection_set(0)
                 self._listbox.activate(0)

    def get(self):
        return self._var.get()

    def set(self, value):
        self._var.set(value)

    @property
    def values(self):
        return self.data

    @values.setter
    def values(self, new_values):
        self.set_data(new_values)
