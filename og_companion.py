"""OG Companion — find libraries, browse their code and build your own programs.

Choose Packages, Documentation or GitHub, then search a library, API or task.
Documentation offers the complete published DevDocs catalogue and topic indexes.
Get code examples reads actual examples from the chosen library or topic.
Choose any example in the selector, edit it, then copy or save your code.
Load a source URL opens examples from another public HTTPS documentation page.
Save all examples exports the loaded collection with source and licence details.
Results are paged; Next results continues beyond the first page.
Downloaded documents are cached for later offline use. The included teaching
examples and CSV-to-JSON foundation also work offline. Custom program generation
and expansion use Ollama with an installed local model, neither of which is
included. Nothing downloaded or generated is installed or executed by the app.
Keep the complete OG Companion folder together when sharing it.
"""
from pathlib import Path
import queue
import re
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, simpledialog
from tkinter.scrolledtext import ScrolledText
import webbrowser

from og_companion_search import (BASE, LANGUAGES, EXTENSIONS, SOURCES, generate_snippet,
                               hydrate_python, installed_models, local_search, search_libraries, starter_program, load_catalogue, package_result)

from og_companion_sources import (DOC_DEFAULTS, documentation_catalogue, documentation_search,
                                  github_search, library_examples, url_examples)

BACKGROUND = '#101312'
SURFACE = '#191f1c'
GREEN = '#93eeac'
SILVER = '#e4eae6'
MUTED = '#a4b6aa'


def configure_display():
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        pass


class OGCompanion(tk.Tk):
    def __init__(self, *, discover_models=True):
        super().__init__()
        self.title('OG Companion | OG Web.site')
        self.geometry('1360x1000')
        self.minsize(1060, 870)
        self.configure(bg=BACKGROUND)
        self.results = queue.Queue()
        self.busy = False
        self.work_epoch = 0
        self.active_work = None
        self.expansion_round = 0
        self.previous_description = ''
        self.selection_token = 0
        self.selected_library = None
        self.entries = []
        self.examples = []
        self.search_context = None
        self.result_page = 1
        self.docsets = documentation_catalogue(online=False)
        self.docset_labels = {d['name']+' '+str(d.get('version') or '')+' ['+d['slug']+']':d for d in self.docsets}
        self.editor_language = 'Python'
        self.editor_dirty = False
        self.highlight_job = None
        self._style()
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        page = ttk.Frame(self, padding=(24, 14, 24, 10))
        page.grid(sticky='nsew');page.columnconfigure(0, weight=1);page.rowconfigure(5, weight=1)
        header = ttk.Frame(page);header.grid(row=0, sticky='ew', pady=(0, 8));header.columnconfigure(0, weight=1)
        ttk.Label(header, text='OG WEB.SITE / DEVELOPER TOOLS', style='Kicker.TLabel').grid(sticky='w')
        ttk.Label(header, text='OG Companion', style='Title.TLabel').grid(row=1, sticky='w')
        ttk.Label(header, text='Find the library. Start the code. Make it yours.', style='Sub.TLabel').grid(row=2, sticky='w', pady=(3, 0))
        logo = BASE / 'og_companion_assets/og-logo.png'
        if logo.exists():
            self.logo = tk.PhotoImage(file=str(logo)).subsample(7, 7)
            ttk.Label(header, image=self.logo).grid(row=0, column=1, rowspan=3, sticky='e', padx=(20, 0))
        icon = BASE / 'og_companion_assets/og-companion.ico'
        if icon.exists():
            try:self.iconbitmap(str(icon))
            except tk.TclError:pass
        settings = ttk.Frame(page);settings.grid(row=1, sticky='ew', pady=(0, 8))
        self.language = tk.StringVar(value='Python')
        ttk.Label(settings, text='LANGUAGE', style='Kicker.TLabel').grid(row=0, column=0, sticky='w')
        self.language_box = ttk.Combobox(settings, textvariable=self.language, values=LANGUAGES, width=18)
        self.language_box.grid(row=1, column=0, sticky='w', padx=(0, 24))
        self.language_box.bind('<<ComboboxSelected>>', self.language_changed)
        self.model = tk.StringVar()
        ttk.Label(settings, text='LOCAL AI MODEL', style='Kicker.TLabel').grid(row=0, column=1, sticky='w')
        self.model_box = ttk.Combobox(settings, textvariable=self.model, width=25)
        self.model_box.grid(row=1, column=1, sticky='w', padx=(0, 10))
        self.models_button = ttk.Button(settings, text='Refresh models', command=self.refresh_models)
        self.models_button.grid(row=1, column=2, sticky='w')
        self.online = tk.BooleanVar(value=True)
        ttk.Checkbutton(settings, text='Search online registries', variable=self.online).grid(row=1, column=3, sticky='e', padx=(20, 0))
        settings.columnconfigure(3, weight=1)
        ttk.Label(page, text='What are you building?', style='Heading.TLabel').grid(row=2, sticky='w')
        self.description = self.text_area(page, 2, font=('Segoe UI', 11), wrap='word')
        self.description.grid(row=3, sticky='ew', pady=(4, 8))
        self.description.insert('1.0', 'I want a program that reads a CSV file, checks for missing values, shows the valid rows and saves them as JSON.')
        buttons = ttk.Frame(page);buttons.grid(row=4, sticky='ew', pady=(0, 8));buttons.columnconfigure(3, weight=1)
        self.search_button = ttk.Button(buttons, text='Find libraries', command=self.search)
        self.search_button.grid(row=0, column=0, sticky='w')
        self.generate_button = ttk.Button(buttons, text='Build / update code', command=self.generate, style='Accent.TButton')
        self.generate_button.grid(row=0, column=1, sticky='w', padx=10)
        self.mode = tk.StringVar(value='Starter program')
        self.mode_box = ttk.Combobox(buttons, textvariable=self.mode, values=('Starter program','Focused snippet'), state='readonly', width=16)
        self.mode_box.grid(row=0, column=2, sticky='w')
        self.clear_search_button = ttk.Button(buttons, text='Clear search', command=self.clear_search)
        self.clear_search_button.grid(row=1,column=0,sticky='w',pady=(6,0))
        self.sources_button=ttk.Button(buttons,text='Refresh documentation',command=self.refresh_sources)
        self.sources_button.grid(row=0,column=3,sticky='e',padx=(0,8))
        ttk.Button(buttons, text='How it works', command=self.help).grid(row=0, column=4, sticky='e')
        panes = ttk.Panedwindow(page, orient='horizontal');panes.grid(row=5, sticky='nsew')
        discovery = ttk.Frame(panes);workbench = ttk.Frame(panes, padding=(22, 0, 0, 0))
        panes.add(discovery, weight=4);panes.add(workbench, weight=7)
        discovery.columnconfigure(0, weight=1);discovery.rowconfigure(4, weight=1)
        ttk.Label(discovery, text='Explore libraries and code', style='Heading.TLabel').grid(row=0, sticky='w')
        source_controls=ttk.Frame(discovery);source_controls.grid(row=1,sticky='ew',pady=(6,4));source_controls.columnconfigure(1,weight=1)
        self.source_mode=tk.StringVar(value='Packages')
        self.source_box=ttk.Combobox(source_controls,textvariable=self.source_mode,values=('Packages','Documentation','GitHub'),state='readonly',width=16)
        self.source_box.grid(row=0,column=0,sticky='w')
        self.source_box.bind('<<ComboboxSelected>>',lambda e:self.source_label.set(self.source_text()))
        self.docset=tk.StringVar()
        self.docset_box=ttk.Combobox(source_controls,textvariable=self.docset,values=list(self.docset_labels),width=24)
        self.docset_box.grid(row=0,column=1,sticky='ew',padx=(6,0))
        self.docset_box.bind('<<ComboboxSelected>>',lambda e:self.source_mode.set('Documentation'))
        self.choose_default_docset()
        keywords=ttk.Frame(discovery);keywords.grid(row=2,sticky='ew',pady=(0,4));keywords.columnconfigure(0,weight=1)
        self.keywords=tk.StringVar()
        ttk.Entry(keywords,textvariable=self.keywords).grid(row=0,column=0,sticky='ew')
        ttk.Button(keywords,text='All API topics',command=lambda:self.search(all_topics=True)).grid(row=0,column=1,padx=(6,0))
        self.source_label=tk.StringVar(value='Optional keywords above · choose a documentation edition to browse its APIs')
        ttk.Label(discovery,textvariable=self.source_label,style='Muted.TLabel',wraplength=440).grid(row=3,sticky='w',pady=(0,5))
        treeframe=ttk.Frame(discovery);treeframe.grid(row=4,sticky='nsew');treeframe.columnconfigure(0,weight=1);treeframe.rowconfigure(0,weight=1)
        self.library_tree=ttk.Treeview(treeframe,columns=('name','source'),show='headings',selectmode='browse',height=6)
        self.library_tree.heading('name',text='Library / API topic');self.library_tree.heading('source',text='Source')
        self.library_tree.column('name',width=245,minwidth=140);self.library_tree.column('source',width=110,minwidth=85)
        self.library_tree.grid(sticky='nsew')
        scroll=ttk.Scrollbar(treeframe,command=self.library_tree.yview);scroll.grid(row=0,column=1,sticky='ns');self.library_tree.configure(yscrollcommand=scroll.set)
        self.library_tree.bind('<<TreeviewSelect>>',self.select_library)
        paging=ttk.Frame(discovery);paging.grid(row=5,sticky='ew',pady=(4,0))
        self.previous_button=ttk.Button(paging,text='Previous results',command=lambda:self.turn_page(-1),state='disabled');self.previous_button.pack(side='left')
        self.next_button=ttk.Button(paging,text='Next results',command=lambda:self.turn_page(1),state='disabled');self.next_button.pack(side='left',padx=6)
        self.library_name=tk.StringVar(value='Choose a library or API topic')
        ttk.Label(discovery,textvariable=self.library_name,style='Heading.TLabel',wraplength=430).grid(row=6,sticky='w',pady=(8,4))
        self.details=self.text_area(discovery,2,font=('Segoe UI',10),wrap='word')
        self.details.grid(row=7,sticky='ew');self.details.configure(state='disabled')
        actions=ttk.Frame(discovery);actions.grid(row=8,sticky='ew',pady=(6,0))
        self.docs_button=ttk.Button(actions,text='Open docs',command=self.open_docs,state='disabled');self.docs_button.pack(side='left')
        self.install_button=ttk.Button(actions,text='Copy install',command=self.copy_install,state='disabled');self.install_button.pack(side='left',padx=6)
        self.examples_button=ttk.Button(actions,text='Get code examples',command=self.get_examples,style='Accent.TButton',state='disabled');self.examples_button.pack(side='left')
        workbench.columnconfigure(0, weight=1);workbench.rowconfigure(3, weight=1)
        editor_head = ttk.Frame(workbench);editor_head.grid(row=0,sticky='ew');editor_head.columnconfigure(0,weight=1)
        ttk.Label(editor_head, text='Your code workbench', style='Heading.TLabel').grid(sticky='w')
        self.code_origin = tk.StringVar(value='Editable starter · Python')
        ttk.Label(workbench, textvariable=self.code_origin, style='Muted.TLabel',wraplength=640).grid(row=1,sticky='w',pady=(4,8))
        example_controls=ttk.Frame(workbench);example_controls.grid(row=2,sticky='ew',pady=(0,6));example_controls.columnconfigure(0,weight=1)
        self.example_name=tk.StringVar(value='Choose Get code examples to browse source code')
        self.example_box=ttk.Combobox(example_controls,textvariable=self.example_name,state='readonly')
        self.example_box.grid(row=0,column=0,sticky='ew');self.example_box.bind('<<ComboboxSelected>>',self.select_example)
        self.url_button=ttk.Button(example_controls,text='Load source URL',command=self.load_url);self.url_button.grid(row=0,column=1,padx=(6,0))
        self.export_button=ttk.Button(example_controls,text='Save all examples',command=self.save_examples,state='disabled');self.export_button.grid(row=0,column=2,padx=(6,0))
        self.output = self.text_area(workbench, 10, font=('Consolas', 11), wrap='none', undo=True)
        self.output.grid(row=3,sticky='nsew')
        horizontal = ttk.Scrollbar(workbench,orient='horizontal',command=self.output.xview)
        horizontal.grid(row=4,sticky='ew');self.output.configure(xscrollcommand=horizontal.set)
        self.output.bind('<<Modified>>', self.code_modified)
        self.output.tag_configure('keyword',foreground='#b7a2fc');self.output.tag_configure('string',foreground='#a5d5a8')
        self.output.tag_configure('comment',foreground='#83a98d');self.output.tag_configure('number',foreground='#efd18d')
        editor_actions=ttk.Frame(workbench);editor_actions.grid(row=5,sticky='ew',pady=(8,0));editor_actions.columnconfigure(2,weight=1)
        self.copy_button=ttk.Button(editor_actions,text='Copy code',command=self.copy);self.copy_button.grid(sticky='w')
        self.save_button=ttk.Button(editor_actions,text='Save code',command=self.save);self.save_button.grid(row=0,column=1,sticky='w',padx=8)
        self.expand_button=ttk.Button(editor_actions,text='Expand code',command=lambda:self.generate(expand=True),style='Accent.TButton')
        self.expand_button.grid(row=0,column=2,sticky='e')
        self.undo_button=ttk.Button(editor_actions,text='Undo update',command=self.undo_update)
        self.undo_button.grid(row=1,column=0,sticky='w',pady=(6,0))
        self.clear_code_button=ttk.Button(editor_actions,text='Clear code',command=self.clear_code)
        self.clear_code_button.grid(row=1,column=1,sticky='w',padx=8,pady=(6,0))
        self.status=tk.StringVar(value='Ready. Browse API documentation or retrieve examples for any package you find.')
        ttk.Label(page,textvariable=self.status,wraplength=1200,style='Status.TLabel').grid(row=6,sticky='ew',pady=(8,0))
        ttk.Label(page,text='OG WEB.SITE   /   Live library examples · DevDocs API browser · Local AI',style='Muted.TLabel').grid(row=7,sticky='w',pady=(6,0))
        self.bind('<Control-Return>',lambda event:self.search())
        self.bind('<Control-Shift-Return>',lambda event:self.generate())
        self.protocol('WM_DELETE_WINDOW',self.close)
        self.show_results(local_search(self.description.get('1.0','end-1c'),'Python'),'Offline examples ready. Find libraries, browse all API topics or load your own documentation URL.')
        self.after(100,self.poll)
        if discover_models:self.after(300,self.refresh_models)

    def _style(self):
        style=ttk.Style(self);style.theme_use('clam')
        style.configure('.',background=BACKGROUND,foreground=SILVER,font=('Segoe UI',10))
        style.configure('TFrame',background=BACKGROUND)
        style.configure('TLabel',background=BACKGROUND,foreground=SILVER)
        style.configure('Title.TLabel',font=('Segoe UI',24,'bold'),foreground=SILVER)
        style.configure('Heading.TLabel',font=('Segoe UI',15,'bold'))
        style.configure('Kicker.TLabel',foreground=GREEN,font=('Segoe UI',9,'bold'))
        style.configure('Sub.TLabel',foreground=MUTED,font=('Segoe UI',10))
        style.configure('Muted.TLabel',foreground=MUTED,font=('Segoe UI',9))
        style.configure('Status.TLabel',foreground=GREEN,font=('Segoe UI',10))
        style.configure('TButton',padding=(12,7),background='#26342b',foreground=SILVER,borderwidth=0)
        style.map('TButton',background=[('active','#3b5343'),('disabled','#202822')],foreground=[('disabled','#6e8174')])
        style.configure('Accent.TButton',background=GREEN,foreground=BACKGROUND,font=('Segoe UI',10,'bold'))
        style.map('Accent.TButton',background=[('active','#c0f7cb'),('disabled','#33463a')])
        style.configure('TCombobox',fieldbackground=SURFACE,background='#304638',foreground=SILVER,arrowcolor=GREEN,padding=6)
        style.configure('TEntry',fieldbackground=SURFACE,foreground=SILVER,insertcolor=GREEN,padding=6)
        style.map('TCombobox',fieldbackground=[('readonly',SURFACE)],foreground=[('readonly',SILVER)])
        style.configure('TCheckbutton',background=BACKGROUND,foreground=MUTED)
        style.map('TCheckbutton',background=[('active',BACKGROUND)])
        style.configure('Treeview',background=SURFACE,fieldbackground=SURFACE,foreground=SILVER,rowheight=30,borderwidth=0)
        style.configure('Treeview.Heading',background='#25352b',foreground=GREEN,padding=6)
        style.map('Treeview',background=[('selected','#375540')],foreground=[('selected','#ffffff')])
        self.option_add('*TCombobox*Listbox.background',SURFACE);self.option_add('*TCombobox*Listbox.foreground',SILVER)

    def text_area(self,parent,height,**kwargs):
        return ScrolledText(parent,height=height,width=32,bg=SURFACE,fg=SILVER,insertbackground=GREEN,
                            selectbackground='#375540',selectforeground='white',borderwidth=0,highlightthickness=1,
                            highlightbackground='#33453a',highlightcolor=GREEN,padx=12,pady=10,**kwargs)

    def choose_default_docset(self):
        slug=DOC_DEFAULTS.get(self.language.get(),'')
        label=next((label for label,d in self.docset_labels.items() if d['slug']==slug),None)
        if not label:
            label=next((label for label,d in self.docset_labels.items() if d['name'].casefold()==self.language.get().casefold()),None)
        self.docset.set(label or next(iter(self.docset_labels)))

    def language_changed(self,event=None):
        self.choose_default_docset();self.source_label.set(self.source_text())

    def source_text(self):
        mode=self.source_mode.get()
        if mode=='Documentation':return 'DevDocs · searchable APIs and examples · downloaded topics stay cached'
        if mode=='GitHub':return 'Public repositories · example code from their README files'
        source=SOURCES.get(self.language.get(),'GitHub repositories')
        return source+' · paged results · load code from the selected package documentation'

    def set_busy(self,value):
        self.busy=value
        for widget in (self.search_button,self.generate_button,self.expand_button,self.clear_code_button,self.models_button,self.language_box,self.model_box,self.url_button,self.sources_button):
            widget.configure(state='disabled' if value else 'normal')
        for widget in (self.mode_box,self.source_box):widget.configure(state='disabled' if value else 'readonly')
        self.docset_box.configure(state='disabled' if value else 'normal')
        self.examples_button.configure(state='normal' if self.selected_library and not value else 'disabled')
        self.update_paging()

    def worker(self,kind,fn):
        if self.busy:return
        self.work_epoch+=1;epoch=self.work_epoch;self.active_work=kind
        self.set_busy(True)
        def work():
            try:self.results.put(('completed',True,(epoch,kind,True,fn())))
            except Exception as error:self.results.put(('completed',True,(epoch,kind,False,str(error))))
        threading.Thread(target=work,daemon=True).start()

    def clear_search(self):
        if self.active_work in ('search','examples'):
            self.work_epoch+=1;self.active_work=None;self.set_busy(False)
        self.selection_token+=1
        self.description.delete('1.0','end');self.keywords.set('')
        self.search_context=None;self.result_page=1;self.entries=[];self.examples=[];self.selected_library=None
        self.library_tree.delete(*self.library_tree.get_children())
        self.library_name.set('Choose a library or API topic');self.set_details('')
        self.example_box.configure(values=[]);self.example_name.set('Choose Get code examples to browse source code')
        for widget in (self.docs_button,self.install_button,self.examples_button,self.export_button):widget.configure(state='disabled')
        self.source_label.set(self.source_text());self.update_paging()
        self.status.set('Search cleared. Your code is retained.'+(' The code request is still running.' if self.active_work=='generate' else ''))

    def clear_code(self):
        if self.busy or not self.can_replace():return
        self.set_code('',self.language.get(),'Empty workbench')
        self.expansion_round=0;self.previous_description=''
        self.status.set('Code cleared. Describe a new program and choose Build / update code.')

    def undo_update(self):
        if self.busy:
            self.status.set('Wait for the code request before undoing an update.');return
        try:self.output.edit_undo()
        except tk.TclError:self.status.set('No earlier code change to undo.');return
        self.editor_dirty=True;self.highlight();self.status.set('Last code change undone. Your earlier code is restored.')

    def search(self,all_topics=False):
        if self.busy:return
        query=self.keywords.get().strip() or self.description.get('1.0','end-1c').strip()
        if all_topics:self.source_mode.set('Documentation');query=''
        language=self.language.get().strip();mode=self.source_mode.get()
        if not language or (not query and mode!='Documentation'):
            self.status.set('Enter a task or keyword and choose a language.');return
        docset=self.docset_labels.get(self.docset.get())
        if mode=='Documentation' and not docset:
            wanted=self.docset.get().strip().casefold()
            matching=[(label,d) for label,d in self.docset_labels.items() if d['name'].casefold()==wanted or d['slug'].casefold()==wanted]
            if matching:
                label,docset=matching[0];self.docset.set(label)
        if mode=='Documentation' and not docset:
            self.status.set('Select a documentation edition from the menu.');return
        self.search_context=(query,language,mode,docset,self.online.get());self.result_page=1
        self.search_page()

    def search_page(self):
        query,language,mode,docset,online=self.search_context;page=self.result_page
        epoch=self.work_epoch+1
        self.source_label.set(self.source_text());self.status.set('Searching '+mode.casefold()+'…')
        def run():
            if mode=='Documentation':return documentation_search(docset,query,page=page,online=online,language=language)
            if mode=='GitHub':
                if not online:raise RuntimeError('GitHub discovery needs online access; previously loaded examples remain cached.')
                return github_search(query,language,page=page)
            return search_libraries(query,language,online,page=page,progress=lambda message:self.results.put(('progress',True,(epoch,message))))
        self.worker('search',run)

    def turn_page(self,step):
        if not self.busy and self.search_context:
            self.result_page=max(1,self.result_page+step);self.search_page()

    def update_paging(self):
        ready=bool(self.search_context and not self.busy and self.search_context[4])
        if self.search_context and self.search_context[2]=='Documentation':ready=not self.busy
        self.previous_button.configure(state='normal' if ready and self.result_page>1 else 'disabled')
        self.next_button.configure(state='normal' if ready and self.entries else 'disabled')

    def get_examples(self):
        if self.busy or not self.selected_library:return
        entry=dict(self.selected_library);online=self.online.get()
        self.status.set('Reading source examples for '+entry['name']+'…')
        if entry.get('snippet'):
            self.show_examples([{'title':entry['name'],'code':entry['snippet'],'language':entry['language'],
                                 'url':entry.get('docs',''),'licence':'Included teaching example','attribution':'OG Companion'}],
                               'Included teaching example ready.');return
        self.worker('examples',lambda:library_examples(entry,online=online))

    def load_url(self):
        if self.busy:return
        url=simpledialog.askstring('Load documentation examples','Public HTTPS documentation page, raw README or GitHub repository URL:',parent=self)
        if not url:return
        language=self.language.get();online=self.online.get()
        self.library_tree.selection_remove(*self.library_tree.selection())
        self.selected_library=package_result(url,language,'Source URL','Public documentation source.','Document',url,'See source documentation')
        self.show_details(self.selected_library)
        self.status.set('Reading examples from your source…')
        self.worker('examples',lambda:url_examples(url.strip(),language,online=online))

    def show_examples(self,examples,status):
        self.examples=examples
        self.example_box.configure(values=[str(i+1)+'. '+e['language']+' · '+e['title'] for i,e in enumerate(examples)])
        self.export_button.configure(state='normal' if examples else 'disabled')
        self.status.set(status if examples else status+'. This page has no readable code blocks; try a usage/tutorial page or another API topic.')
        if examples:
            wanted=self.selected_library['language'] if self.selected_library else self.language.get()
            preferred=next((i for i,e in enumerate(examples) if e['language']==wanted),
                           next((i for i,e in enumerate(examples) if e['language'].startswith(wanted)),0))
            self.example_box.current(preferred);self.select_example()
        else:self.example_name.set('No code blocks found · your workbench is retained')

    def select_example(self,event=None):
        index=self.example_box.current()
        if index<0 or index>=len(self.examples):return
        example=self.examples[index]
        if not self.can_replace():return
        self.set_code(example['code'],example['language'],'Source example · '+example['url'])
        self.editor_dirty=True
        self.status.set(str(len(self.examples))+' loaded source blocks · Editable '+example['language']+' · '+example.get('licence','See source terms')[:120]+' · '+example.get('attribution','')[:100])

    def save_examples(self):
        if not self.examples:return
        path=filedialog.asksaveasfilename(defaultextension='.json',initialfile='OG Companion - Source Examples.json',filetypes=[('Code and source references','*.json')])
        if path:
            import json
            try:Path(path).write_text(json.dumps({'examples':self.examples},ensure_ascii=False,indent=2),encoding='utf-8')
            except OSError as error:messagebox.showerror('Save failed',str(error))
            else:self.status.set('All '+str(len(self.examples))+' loaded examples saved with their source and licence details.')

    def refresh_models(self):
        if self.busy:return
        self.worker('models',installed_models)

    def refresh_sources(self):
        if self.busy:return
        if not self.online.get():
            self.status.set('Enable online access to refresh the documentation catalogue. Existing editions remain available.');return
        self.status.set('Refreshing the published documentation catalogue…')
        self.worker('docsets',lambda:documentation_catalogue(online=True))

    def generate(self,expand=False):
        if self.busy:return
        description=self.description.get('1.0','end-1c').strip();language=self.language.get().strip();model=self.model.get().strip()
        existing=self.output.get('1.0','end-1c')
        if expand and not existing.strip():
            self.status.set('Build or load code before expanding it.');return
        if existing.strip() and language!=self.editor_language:
            self.status.set('Your current code is '+self.editor_language+'. Choose that language to update it, or save and clear the code to start in '+language+'.');return
        if expand and not description:description=self.previous_description or 'Add a useful working feature to this program while keeping its existing behaviour.'
        if not description or not language:
            self.status.set('Describe your program and choose a language.');return
        program_mode=self.mode.get()=='Starter program'
        blueprint=starter_program(description,language) if program_mode and not existing.strip() else None
        if blueprint:
            self.set_code(blueprint[0],language,'Built-in starter program · '+blueprint[1]);self.editor_dirty=True
            self.previous_description=description;self.expansion_round=0
            self.status.set('CSV-to-JSON foundation ready: read, check, display and save. Edit its functions to add your own rules.');return
        entry=dict(self.selected_library) if self.selected_library else None
        if entry and self.examples:
            entry['reference_examples']=[{'code':e['code'][:5000],'source':e['url'],'language':e['language']} for e in self.examples if e['language']==language][:3]
        self.generation_baseline=existing
        round_number=self.expansion_round+1 if existing.strip() else 0
        previous=self.previous_description
        self.status.set('Local AI is '+('updating your current code' if existing.strip() else 'building your starting code')+'…')
        def run():
            chosen=model
            if not chosen:
                models=installed_models()
                if not models:raise RuntimeError('Custom building and expansion need Ollama with an installed model. Your current code is retained.')
                chosen=models[0]
            code=generate_snippet(description,language,chosen,entry,existing,
                                  program_mode=program_mode,expansion_round=round_number,previous_description=previous,additional_feature=expand)
            return code,language,description,round_number,chosen
        self.worker('generate',run)

    def show_results(self,entries,status):
        self.entries=entries;self.selection_token+=1;self.selected_library=None
        self.library_tree.delete(*self.library_tree.get_children())
        for i,entry in enumerate(entries):self.library_tree.insert('', 'end',iid=str(i),values=(entry['name'],entry['source']))
        self.status.set(status if entries else 'No matches. Try a shorter library keyword, change language or create a snippet with local AI. '+status)
        self.update_paging()
        if entries:self.library_tree.selection_set('0')
        else:
            self.library_name.set('No library selected');self.set_details('Your current code is retained. Try a package name such as pandas, express or serde.');self.docs_button.configure(state='disabled');self.install_button.configure(state='disabled')
            self.examples=[];self.example_box.configure(values=[]);self.example_name.set('No library selected')
            self.examples_button.configure(state='disabled');self.export_button.configure(state='disabled')

    def select_library(self,event=None):
        selected=self.library_tree.selection()
        if not selected:return
        entry=self.entries[int(selected[0])];self.selection_token+=1;token=self.selection_token
        self.examples=[];self.example_box.configure(values=[])
        self.example_name.set('Get code examples for this selection');self.export_button.configure(state='disabled')
        self.selected_library=entry;self.show_details(entry)
        self.examples_button.configure(state='normal' if not self.busy else 'disabled')
        if entry['source']=='PyPI':
            def load():
                try:self.results.put(('details',True,(token,hydrate_python(entry))))
                except Exception as error:self.results.put(('details',False,(token,str(error))))
            threading.Thread(target=load,daemon=True).start()

    def show_details(self,entry):
        self.library_name.set(entry['name'] if len(entry['name'])<=64 else entry['name'][:61]+'…')
        self.set_details(entry['description']+'\n\n'+entry['source']+' · '+entry['version']+'\n\n'+entry['install'])
        self.docs_button.configure(state='normal' if entry.get('docs') else 'disabled')
        self.install_button.configure(state='normal' if entry.get('install') else 'disabled')

    def set_details(self,value):
        self.details.configure(state='normal');self.details.delete('1.0','end');self.details.insert('1.0',value);self.details.configure(state='disabled')

    def can_replace(self):
        return not self.editor_dirty or messagebox.askyesno('Keep your edits?', 'Replace the code currently in your workbench? Copy or save it first if you want to keep it.')

    def set_code(self,code,language,origin,*,keep_undo=False):
        if keep_undo:self.output.edit_separator();self.output.configure(autoseparators=False)
        self.output.delete('1.0','end');self.output.insert('1.0',code)
        if keep_undo:self.output.edit_separator();self.output.configure(autoseparators=True)
        else:self.output.edit_reset();self.expansion_round=0;self.previous_description=''
        self.output.edit_modified(False)
        self.editor_dirty=False;self.editor_language=language;self.code_origin.set(origin+' · '+language);self.highlight()

    def code_modified(self,event=None):
        if self.output.edit_modified():
            self.editor_dirty=True;self.output.edit_modified(False)
            if self.highlight_job:self.after_cancel(self.highlight_job)
            self.highlight_job=self.after(150,self.highlight)

    def highlight(self):
        self.highlight_job=None;code=self.output.get('1.0','end-1c')
        for tag in ('keyword','string','comment','number'):self.output.tag_remove(tag,'1.0','end')
        patterns={'keyword':r'\b(?:import|from|as|def|class|return|if|else|elif|for|while|with|try|except|raise|async|await|const|let|function|public|static|void|var|using|fn|use|package|func|SELECT|FROM|WHERE|CREATE|INSERT)\b',
                  'number':r'\b\d+(?:\.\d+)?\b','string':r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'',
                  'comment':r'(?m)^\s*(?:#|//|--).*|(?<=\s)#.*'}
        for tag,pattern in patterns.items():
            for match in re.finditer(pattern,code):self.output.tag_add(tag,f'1.0+{match.start()}c',f'1.0+{match.end()}c')

    def poll(self):
        while True:
            try:kind,success,value=self.results.get_nowait()
            except queue.Empty:break
            if kind=='progress':
                epoch,message=value
                if epoch==self.work_epoch:self.status.set(message)
                continue
            if kind=='details':
                token,result=value
                if token==self.selection_token:
                    if success:self.selected_library=result;self.show_details(result)
                    else:self.set_details(self.selected_library['description']+'\n\nMetadata unavailable: '+result)
                continue
            if kind=='completed':
                epoch,kind,success,value=value
                if epoch!=self.work_epoch:continue
                self.active_work=None
            self.set_busy(False)
            if kind=='models':
                if success and value:
                    self.model_box.configure(values=value)
                    if self.model.get() not in value:self.model.set(value[0])
                    self.status.set('Local AI ready · '+self.model.get()+'. Search libraries or describe your next task.')
                else:self.status.set('Source examples and documentation are ready. Local AI generation needs Ollama and an installed model.')
            elif not success:self.status.set('Could not complete the request: '+value)
            elif kind=='docsets':
                previous=self.docset.get();self.docsets=value
                self.docset_labels={d['name']+' '+str(d.get('version') or '')+' ['+d['slug']+']':d for d in value}
                self.docset_box.configure(values=list(self.docset_labels))
                if previous not in self.docset_labels:self.choose_default_docset()
                self.status.set(str(len(value))+' documentation editions available. Select an edition and search its API topics.')
            elif kind=='search':self.show_results(*value)
            elif kind=='examples':self.show_examples(*value)
            elif kind=='generate':
                if self.output.get('1.0','end-1c')!=self.generation_baseline and not messagebox.askyesno('Newer code changes','Your code changed while the request was running. Replace those newer changes with this result?'):
                    self.status.set('Your newer workbench edits are retained. Generate again when you are ready.');continue
                self.set_code(value[0],value[1],'Local AI suggestion',keep_undo=True);self.editor_dirty=True
                self.previous_description=value[2];self.expansion_round=value[3];self.model.set(value[4])
                self.status.set(('Code update '+str(self.expansion_round)+' ready.' if self.expansion_round else 'Starting code ready.')+' You can change the description and update again, or undo. Test the code before using it.')
        self.after(100,self.poll)

    def open_docs(self):
        from urllib.parse import urlparse
        url=self.selected_library.get('docs','') if self.selected_library else ''
        if urlparse(url).scheme in ('http','https'):webbrowser.open(url)
        else:self.status.set('No usable web documentation address was supplied.')

    def copy_install(self):
        if self.selected_library:
            self.clipboard_clear();self.clipboard_append(self.selected_library['install']);self.status.set('Installation guidance copied. No packages have been installed.')

    def copy(self):
        text=self.output.get('1.0','end-1c')
        if not text.strip():self.status.set('Open or create a snippet first.');return
        self.clipboard_clear();self.clipboard_append(text);self.status.set('Your current code copied, including edits.')

    def save(self):
        text=self.output.get('1.0','end-1c')
        if not text.strip():self.status.set('Open or create a snippet first.');return
        ext=EXTENSIONS.get(self.editor_language,'.txt')
        path=filedialog.asksaveasfilename(defaultextension=ext,initialfile='og-starter'+ext,filetypes=[('Source code','*'+ext),('All files','*.*')])
        if path:
            try:Path(path).write_text(text.rstrip()+'\n',encoding='utf-8')
            except OSError as error:messagebox.showerror('Save failed',str(error))
            else:self.editor_dirty=False;self.status.set('Code saved with your edits.')

    def help(self):
        import json
        inventory=json.loads((BASE/'og_companion_assets/content-inventory.json').read_text(encoding='utf-8'))
        included=inventory['included'];docs=inventory['documentation']
        counts=(f"\n\nChecked content inventory ({inventory['verified_at'][:10]}):\n"
                f"{included['teaching_snippets']} supplied teaching snippets; {included['complete_program_foundations']} complete foundation.\n"
                f"{docs['distinct_collection_titles']} documentation collection titles across {docs['editions']} editions.\n"
                f"{inventory['pypi']['package_names_in_verified_index']:,} names in the checked PyPI index (downloaded separately).\n"
                'Online snippet total: not measured. Each loaded source shows its actual block count.\n'
                'The Read Me gives the full counts and their meaning.')
        messagebox.showinfo('OG Companion — Guide and content counts',__doc__+counts)

    def close(self):
        if self.editor_dirty and not messagebox.askyesno('Unsaved code','Close without saving your workbench edits?'):return
        self.destroy()

    def destroy(self):
        for job in self.tk.call('after','info'):
            self.after_cancel(job)
        super().destroy()


def check_installation(report_path, *, online=False):
    """Check the portable installation without network access or a model."""
    import ast
    import json
    report={}
    app=None
    try:
        app=OGCompanion(discover_models=False);app.withdraw();app.update()
        report['application_title']=app.title()
        report['catalogue_entries']=len(load_catalogue())
        report['documentation_editions']=len(app.docsets)
        report['source_browser_loaded']=all(hasattr(app,name) for name in ('example_box','source_box','docset_box','next_button','examples_button'))
        report['workbench_controls_loaded']=all(hasattr(app,name) for name in ('clear_search_button','expand_button','clear_code_button','undo_button'))
        report['logo_loaded']=hasattr(app,'logo')
        app.generate();app.update()
        code=app.output.get('1.0','end-1c');ast.parse(code)
        report['starter_program_loaded']='def valid_row' in code and 'Built-in starter program' in app.code_origin.get()
        report['runtime_location']=str(BASE)
        app.clear_search_button.invoke();app.update()
        report['clear_search_preserves_program']=app.output.get('1.0','end-1c')==code and not app.entries and not app.description.get('1.0','end-1c')
        app.set_code(code+'\n# Installation undo check\n','Python','Check',keep_undo=True)
        app.undo_button.invoke();app.update()
        report['undo_restores_program']=app.output.get('1.0','end-1c')==code
        report['passed']=bool(report['logo_loaded'] and report['documentation_editions']>100 and report['source_browser_loaded'] and report['starter_program_loaded'] and report['workbench_controls_loaded'] and report['clear_search_preserves_program'] and report['undo_restores_program'])
        if online:
            from og_companion_sources import fetch_text,extract_examples
            text,url,_=fetch_text('https://documents.devdocs.io/python~3.14/library/csv.html')
            report['online_document_examples']=len(extract_examples(text,url,'Python'))
            entry=package_result('axios','JavaScript','npm','HTTP client','Live','https://axios-http.com','npm install axios','https://www.npmjs.com/package/axios')
            examples,_=library_examples(entry)
            report['package_source_examples']=len(examples)
            report['passed']=report['passed'] and report['online_document_examples']>0 and report['package_source_examples']>30
    except Exception as error:
        report.update(passed=False,error=str(error))
    finally:
        if app is not None:app.destroy()
    Path(report_path).write_text(json.dumps(report,indent=2),encoding='utf-8')
    return 0 if report['passed'] else 1


if __name__=='__main__':
    import sys
    configure_display()
    if len(sys.argv)==3 and sys.argv[1] in ('--check-installation','--check-online-sources'):
        raise SystemExit(check_installation(sys.argv[2],online=sys.argv[1]=='--check-online-sources'))
    OGCompanion().mainloop()
