"""OG Companion: build code, browse libraries and connect your local models."""
from pathlib import Path
import ast
import json
import queue
import sys
import threading
import re
import webbrowser
from PySide6.QtCore import Qt, QRect, QTimer
from PySide6.QtGui import QColor, QFont, QIcon, QKeySequence, QPainter, QPixmap, QShortcut, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import (QApplication,QCheckBox,QComboBox,QFileDialog,QHBoxLayout,
    QHeaderView,QInputDialog,QLabel,QLineEdit,QMainWindow,QMessageBox,QPlainTextEdit,QPushButton,
    QSplitter,QTabWidget,QTableWidget,QTableWidgetItem,QTreeWidget,QTreeWidgetItem,QVBoxLayout,QWidget)
from og_companion_search import (BASE,EXTENSIONS,LANGUAGES,connect_local_model,discover_models,
    generate_snippet,hydrate_python,load_catalogue,local_endpoint,package_result,search_libraries,
    starter_program,task_guidance,task_libraries,task_terms,set_service_token)
from og_companion_sources import (DOC_DEFAULTS,collection_examples,documentation_catalogue,
    documentation_search,github_search,library_examples,url_examples)

_qt_application=None
def application():
    global _qt_application
    if QApplication.instance() is None:
        _qt_application=QApplication(sys.argv[:1]);_qt_application.setApplicationName('OG Companion')
        _qt_application.setOrganizationName('OG Web.site');_qt_application.setStyle('Fusion')
    return QApplication.instance()

class BrandSurface(QWidget):
    def __init__(self):
        super().__init__();self.logo=QPixmap(str(BASE/'og_companion_assets/OG Code Companion logo.png'));self.logo_rect=QRect()
    def paintEvent(self,event):
        painter=QPainter(self);painter.fillRect(self.rect(),QColor('#060a08'))
        side=max(1,min(self.width(),self.height())-24)
        self.logo_rect=QRect((self.width()-side)//2,(self.height()-side)//2,side,side)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform);painter.setOpacity(.42)
        painter.drawPixmap(self.logo_rect,self.logo,self.logo.rect())

STYLE="""
QWidget { color:#eff7f2; background:transparent; font-family:'Segoe UI'; font-size:15px; }
QPlainTextEdit#code { font-family:'Consolas'; font-size:17px; }
QLabel#title { font-size:29px; font-weight:650; }
QLabel#brand { color:#a3ffbe; font-size:12px; font-weight:600; }
QLabel#status { color:#b9ffcd; font-size:13px; }
QPushButton { background:rgba(9,20,14,165); border:1px solid rgba(150,220,180,90); padding:8px 14px; }
QPushButton:hover { background:rgba(48,86,62,210); border-color:#a3ffbe; }
QPushButton:disabled { color:#82998b; border-color:rgba(150,220,180,35); }
QPushButton#accent { background:#a3ffbe; color:#08140d; font-weight:650; border-color:#a3ffbe; }
QComboBox { background:rgba(7,15,10,170); border:1px solid rgba(150,220,180,90); padding:7px; min-width:120px; }
QComboBox QAbstractItemView { background:#111e16; selection-background-color:#294b36; color:#eff7f2; }
QPlainTextEdit,QTreeWidget,QTableWidget { background:rgba(4,12,8,135); border:1px solid rgba(150,220,180,75); padding:8px; selection-background-color:#315a40; }
QPlainTextEdit#brief { background:rgba(4,12,8,160); }
QHeaderView::section { background:rgba(7,20,12,200); color:#b9ffcd; border:0; padding:7px; }
QTabWidget::pane { border:0; background:transparent; }
QTabBar::tab { background:rgba(4,12,8,155); padding:11px 20px; margin-right:4px; border-bottom:2px solid transparent; }
QTabBar::tab:selected { color:#b9ffcd; border-bottom-color:#a3ffbe; background:rgba(20,43,29,175); }
QScrollBar:vertical { background:rgba(4,12,8,100); width:11px; }
QScrollBar:horizontal { background:rgba(4,12,8,100); height:11px; }
QScrollBar::handle { background:rgba(160,230,185,120); min-height:25px; min-width:25px; }
QScrollBar::add-line,QScrollBar::sub-line { width:0; height:0; }
QSplitter::handle { background:transparent; width:14px; }
QMessageBox,QInputDialog { background:#111e16; }
"""
def row(parent,*widgets):
    layout=QHBoxLayout();layout.setSpacing(10)
    for widget in widgets:
        if widget is None:layout.addStretch()
        else:layout.addWidget(widget)
    parent.addLayout(layout);return layout
def button(text,callback,accent=False):
    control=QPushButton(text)
    if accent:control.setObjectName('accent')
    control.clicked.connect(lambda checked=False:callback());return control

class CodeColours(QSyntaxHighlighter):
    def highlightBlock(self,text):
        patterns=[(r'\b(?:import|from|as|def|class|return|if|else|elif|for|while|with|try|except|raise|async|await|const|let|function|public|static|void|var|using|fn|use|package|func|SELECT|FROM|WHERE|CREATE|INSERT)\b','#d9bfff'),
                  (r'\b\d+(?:\.\d+)?\b','#ffe2a8'),
                  (r'"(?:[^"\\]|\\.)*"|\x27(?:[^\x27\\]|\\.)*\x27','#b1ffd0'),
                  (r'^\s*(?:#|//|--).*|\s#.*','#bfd4c8')]
        for pattern,colour in patterns:
            style=QTextCharFormat();style.setForeground(QColor(colour))
            for match in re.finditer(pattern,text):self.setFormat(match.start(),len(match.group()),style)

class OGCompanion(QMainWindow):
    def __init__(self,*,discover_models=True):
        application();super().__init__();self.setWindowTitle('OG Companion | OG Web.site')
        available=application().primaryScreen().availableGeometry()
        self.resize(min(1280,available.width()-96),min(780,available.height()-96));self.setMinimumSize(960,700);self.setStyleSheet(STYLE)
        self.placement_path=Path.home()/'.og-companion'/'window.json';self.placement={};self.initial_placement_done=False
        try:self.placement=json.loads(self.placement_path.read_text(encoding='utf-8'))
        except (OSError,ValueError):pass
        self.setWindowIcon(QIcon(str(BASE/'og_companion_assets/OG Code Companion logo.ico')))
        self.results=queue.Queue();self.busy=False;self.models_loading=False;self.disposed=False
        self.work_epoch=0;self.active_work=None;self.selection_token=0;self.expansion_round=0
        self.previous_description='';self.connected_model=None;self.model_records=[];self.entries=[]
        self.examples=[];self.selected_library=None;self.search_context=None;self.result_page=1
        self.editor_language='Python';self.editor_dirty=False;self.history=[];self.setting_code=False
        self.settings_path=Path.home()/'.og-companion'/'model-services.json';self.extra_endpoints=[]
        try:self.extra_endpoints=json.loads(self.settings_path.read_text(encoding='utf-8')).get('endpoints',[])
        except (OSError,ValueError):pass
        self.surface=BrandSurface();self.setCentralWidget(self.surface)
        page=QVBoxLayout(self.surface);page.setContentsMargins(24,16,24,14);page.setSpacing(8)
        title=QLabel('OG Companion');title.setObjectName('title');brand=QLabel('OG WEB.SITE / DEVELOPER TOOLS');brand.setObjectName('brand')
        row(page,title,None,brand);self.tabs=QTabWidget();page.addWidget(self.tabs,1)
        self.build_tab();self.libraries_tab();self.models_tab()
        self.status=QLabel('Describe what you want to build, then choose Get starter code.');self.status.setObjectName('status');self.status.setWordWrap(True);page.addWidget(self.status)
        self.timer=QTimer(self);self.timer.timeout.connect(self.poll);self.timer.start(100)
        self.build_shortcut=QShortcut(QKeySequence('Ctrl+Return'),self);self.build_shortcut.activated.connect(self.generate)
        self.save_shortcut=QShortcut(QKeySequence('Ctrl+S'),self);self.save_shortcut.activated.connect(self.save)
        supplied=[dict(e,language='Python',source='Starter library',version='Example',registry_url=e['docs']) for e in load_catalogue() if 'Python' in e['languages']]
        self.show_results(supplied,'Describe what you want to build, then choose Get starter code.')
        self.set_guidance('Describe your program in your own words. Get starter code provides a supported offline foundation, a reference snippet or a custom program from a model you connect. Browse libraries retrieves documentation and examples independently of AI. Edit the Code tab, save your version and develop it one feature at a time.')
        self.description.setFocus()
        if discover_models:QTimer.singleShot(250,self.refresh_models)
    def page(self,title):
        page=QWidget();layout=QVBoxLayout(page);layout.setContentsMargins(0,10,0,0);layout.setSpacing(8);self.tabs.addTab(page,title);return layout
    def build_tab(self):
        page=self.page('Build code');self.language_box=QComboBox();self.language_box.setEditable(True);self.language_box.addItems(LANGUAGES)
        self.language_box.currentTextChanged.connect(self.language_changed);self.mode_box=QComboBox();self.mode_box.addItems(['Starter program','Focused snippet'])
        self.connection_label=QLabel('Reference code available · no model connected');self.connection_label.setWordWrap(True)
        row(page,QLabel('Language'),self.language_box,QLabel('Output'),self.mode_box,None,self.connection_label)
        page.addWidget(QLabel('What would you like to build?'));self.description=QPlainTextEdit();self.description.setObjectName('brief');self.description.setFixedHeight(64)
        self.description.setPlaceholderText('Describe the program, or paste code and explain what you need.');page.addWidget(self.description)
        self.generate_button=button('Get starter code / Update',self.generate,True);self.clear_search_button=button('New request',self.clear_search)
        row(page,self.generate_button,self.clear_search_button,None)
        self.suggestions=QLabel('Browse libraries for packages and source examples.');self.suggestions.setWordWrap(True);page.addWidget(self.suggestions)
        self.workbench_tabs=QTabWidget();page.addWidget(self.workbench_tabs,1)
        self.output=QPlainTextEdit();self.output.setObjectName('code');self.output.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap);self.output.textChanged.connect(self.code_modified)
        self.code_colours=CodeColours(self.output.document())
        self.guidance=QPlainTextEdit();self.guidance.setReadOnly(True);self.workbench_tabs.addTab(self.output,'Code');self.workbench_tabs.addTab(self.guidance,'How to build it')
        self.code_origin=QLabel('Editable workbench · Python');self.code_origin.setWordWrap(True);page.addWidget(self.code_origin)
        self.copy_button=button('Copy code',self.copy);self.save_button=button('Save code',self.save);self.expand_button=button('Expand code',lambda:self.generate(expand=True))
        self.undo_button=button('Undo update',self.undo_update);self.clear_code_button=button('Clear code',self.clear_code)
        row(page,self.copy_button,self.save_button,self.undo_button,self.clear_code_button,None,self.expand_button)
    def libraries_tab(self):
        page=self.page('Browse libraries');self.docsets=documentation_catalogue(online=False)
        self.docset_labels={d['name']+' '+str(d.get('version') or '')+' ['+d['slug']+']':d for d in self.docsets}
        self.source_box=QComboBox();self.source_box.addItems(['Packages','Documentation','GitHub'])
        self.docset_box=QComboBox();self.docset_box.setEditable(True);self.docset_box.addItems(list(self.docset_labels));self.docset_box.setMinimumWidth(250)
        self.docset_box.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon);self.docset_box.setMinimumContentsLength(16)
        self.docset_box.activated.connect(lambda index:self.source_box.setCurrentText('Documentation'))
        self.online=QCheckBox('Online sources');self.online.setChecked(True);row(page,self.source_box,self.docset_box,None,self.online)
        self.keywords=QPlainTextEdit();self.keywords.setFixedHeight(48);self.keywords.setPlaceholderText('Exact library name, API or task keywords')
        self.search_button=button('Find libraries',self.search,True);self.collection_button=button('Complete collection',self.get_collection);self.sources_button=button('Refresh catalogue',self.refresh_sources)
        row(page,self.keywords,self.search_button,self.collection_button,self.sources_button)
        split=QSplitter();page.addWidget(split,1);self.library_tree=QTreeWidget();self.library_tree.setHeaderLabels(['Library / API topic','Source'])
        self.library_tree.itemSelectionChanged.connect(self.select_library);self.library_tree.itemDoubleClicked.connect(lambda item,column:self.get_examples())
        self.library_tree.header().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch);split.addWidget(self.library_tree)
        panel=QWidget();details=QVBoxLayout(panel);details.setContentsMargins(10,0,0,0);details.setSpacing(12)
        self.library_name=QLabel('Choose a library');self.library_name.setWordWrap(True);details.addWidget(self.library_name);self.details=QPlainTextEdit();self.details.setReadOnly(True);details.addWidget(self.details,1)
        self.docs_button=button('Open docs',self.open_docs);self.install_button=button('Copy install',self.copy_install);self.examples_button=button('Get code examples',self.get_examples,True)
        row(details,self.docs_button,self.install_button,self.examples_button);self.example_box=QComboBox();self.example_box.activated.connect(self.select_example);details.addWidget(self.example_box)
        self.url_button=button('Load source URL',self.load_url);self.export_button=button('Save all examples',self.save_examples);row(details,self.url_button,self.export_button)
        split.addWidget(panel);split.setSizes([450,650]);self.previous_button=button('Previous results',lambda:self.turn_page(-1));self.next_button=button('Next results',lambda:self.turn_page(1))
        self.topics_button=button('All API topics',lambda:self.search(all_topics=True));row(page,self.previous_button,self.next_button,None,self.topics_button);self.choose_default_docset()
    def models_tab(self):
        page=self.page('Local models');intro=QLabel('Choose a model from your own computer, then connect it. Library examples and supplied starters work without AI.');intro.setWordWrap(True);page.addWidget(intro)
        self.models_button=button('Refresh models',self.refresh_models);self.endpoint_button=button('Add service URL',self.add_model_endpoint)
        self.token_button=button('Service token',self.add_service_token)
        self.connect_button=button('Connect selected model',self.connect_model,True);self.disconnect_button=button('Disconnect',self.disconnect_model)
        row(page,self.models_button,self.endpoint_button,self.token_button,None,self.connect_button,self.disconnect_button)
        self.model_table=QTableWidget(0,4);self.model_table.setHorizontalHeaderLabels(['Model','Provider','Local service','State'])
        self.model_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows);self.model_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection);self.model_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.model_table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch);self.model_table.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeMode.ResizeToContents);page.addWidget(self.model_table,1)
        self.model_note=QLabel('Discover Ollama, LM Studio and compatible localhost services. A service must be running to use its models.');self.model_note.setWordWrap(True);page.addWidget(self.model_note)
    def choose_default_docset(self):
        slug=DOC_DEFAULTS.get(self.language_box.currentText(),'');label=next((label for label,d in self.docset_labels.items() if d['slug']==slug),None)
        if label:self.docset_box.setCurrentText(label)
    def language_changed(self,language):
        if hasattr(self,'docset_box'):self.choose_default_docset()
    def showEvent(self,event):
        super().showEvent(event)
        if not self.initial_placement_done:
            self.initial_placement_done=True;QTimer.singleShot(0,self.ensure_on_screen)
    def ensure_on_screen(self):
        if self.disposed:return
        screen=next((s for s in application().screens() if s.name()==self.placement.get('screen')),self.screen() or application().primaryScreen())
        work=screen.availableGeometry();frame=self.frameGeometry();margin=24
        extra_width=max(0,frame.width()-self.width());extra_height=max(0,frame.height()-self.height())
        max_width=max(200,work.width()-margin*2-extra_width);max_height=max(200,work.height()-margin*2-extra_height)
        self.setMinimumSize(min(960,max_width),min(700,max_height));self.resize(min(self.width(),max_width),min(self.height(),max_height))
        width=self.width()+extra_width;height=self.height()+extra_height
        self.move(work.left()+max(margin,(work.width()-width)//2),work.top()+max(margin,(work.height()-height)//2))
    def set_guidance(self,text):self.guidance.setPlainText(text)
    def set_busy(self,value):
        self.busy=value
        for control in (self.generate_button,self.search_button,self.expand_button,self.collection_button,self.sources_button,self.url_button,self.examples_button):control.setEnabled(not value)
        self.update_paging()
    def worker(self,kind,fn):
        if self.busy:return
        self.work_epoch+=1;epoch=self.work_epoch;self.active_work=kind;self.set_busy(True)
        def run():
            try:self.results.put(('completed',True,(epoch,kind,True,fn())))
            except Exception as error:self.results.put(('completed',True,(epoch,kind,False,str(error))))
        threading.Thread(target=run,daemon=True).start()
    def clear_search(self):
        if self.active_work in ('search','examples','task_reference'):self.work_epoch+=1;self.active_work=None;self.set_busy(False)
        self.selection_token+=1;self.description.clear();self.keywords.clear();self.search_context=None;self.result_page=1;self.entries=[];self.examples=[];self.selected_library=None
        self.library_tree.clear();self.example_box.clear();self.details.clear();self.library_name.setText('Choose a library');self.update_paging()
        self.suggestions.setText('New request ready. Your code is retained.');self.status.setText('Request cleared. Your code is retained.');self.description.setFocus()
    def clear_code(self):
        if self.busy or not self.can_replace():return
        self.set_code('',self.language_box.currentText(),'Empty workbench');self.previous_description='';self.expansion_round=0;self.status.setText('Code cleared. Describe the next program.')
    def undo_update(self):
        if self.busy:self.status.setText('Wait for the current request before undoing.');return
        if not self.history:self.status.setText('No previous code update to undo.');return
        code,language,origin=self.history.pop();self.set_code(code,language,origin,reset_history=False);self.editor_dirty=True;self.status.setText('Previous code restored.')
    def search(self,all_topics=False):
        if self.busy:return
        query=self.keywords.toPlainText().strip() or ' '.join(sorted(task_terms(self.description.toPlainText())))
        if all_topics:self.source_box.setCurrentText('Documentation');query=''
        language=self.language_box.currentText().strip();mode=self.source_box.currentText();docset=self.docset_labels.get(self.docset_box.currentText())
        if mode=='Documentation' and not docset:self.status.setText('Choose a documentation edition from the menu.');return
        if not query and mode!='Documentation':self.status.setText('Enter a library name or describe your task.');return
        self.search_context=(query,language,mode,docset,self.online.isChecked());self.result_page=1;self.search_page()
    def search_page(self):
        query,language,mode,docset,online=self.search_context;page=self.result_page;self.status.setText('Searching '+mode.casefold()+'…')
        def run():
            if mode=='Documentation':return documentation_search(docset,query,page=page,online=online,language=language)
            if mode=='GitHub':
                if not online:raise RuntimeError('Repository discovery needs online access.')
                return github_search(query,language,page=page)
            return search_libraries(query,language,online,page=page)
        self.worker('search',run)
    def turn_page(self,step):
        if not self.busy and self.search_context:self.result_page=max(1,self.result_page+step);self.search_page()
    def update_paging(self):
        ready=bool(self.search_context and not self.busy and (self.search_context[4] or self.search_context[2]=='Documentation'))
        self.previous_button.setEnabled(ready and self.result_page>1);self.next_button.setEnabled(ready and bool(self.entries))
    def show_results(self,entries,status):
        self.entries=entries;self.selection_token+=1;self.selected_library=None;self.library_tree.clear()
        for i,entry in enumerate(entries):
            item=QTreeWidgetItem([entry['name'],entry['source']]);item.setData(0,Qt.ItemDataRole.UserRole,i);self.library_tree.addTopLevelItem(item)
        self.status.setText(status);self.update_paging();self.suggestions.setText('Suggested libraries: '+', '.join(e['name'] for e in entries[:5]) if entries else 'Browse an exact library or connect a local model for custom code.')
        if entries:self.library_tree.setCurrentItem(self.library_tree.topLevelItem(0))
        else:self.details.clear();self.library_name.setText('No matching library');self.examples=[];self.example_box.clear()
        self.examples_button.setEnabled(bool(entries) and not self.busy);self.export_button.setEnabled(bool(self.examples))
    def select_library(self):
        item=self.library_tree.currentItem()
        if item is None:return
        index=item.data(0,Qt.ItemDataRole.UserRole)
        if index is None or index>=len(self.entries):return
        entry=self.entries[index]
        if entry==self.selected_library:return
        self.selection_token+=1;token=self.selection_token;self.selected_library=entry;self.examples=[];self.example_box.clear();self.export_button.setEnabled(False);self.show_details(entry)
        if entry['source']=='PyPI':
            def run():
                try:self.results.put(('details',True,(token,hydrate_python(entry))))
                except Exception as error:self.results.put(('details',False,(token,str(error))))
            threading.Thread(target=run,daemon=True).start()
    def show_details(self,entry):
        self.library_name.setText(entry['name']);self.details.setPlainText(entry['description']+'\n\n'+entry['source']+' · '+entry['version']+'\n\n'+entry['install'])
    def get_examples(self):
        if self.busy or not self.selected_library:return
        entry=dict(self.selected_library);online=self.online.isChecked();self.status.setText('Loading examples for '+entry['name']+'…');self.worker('examples',lambda:library_examples(entry,online=online))
    def get_collection(self):
        if self.busy:return
        docset=self.docset_labels.get(self.docset_box.currentText());online=self.online.isChecked()
        if not docset:self.status.setText('Choose a documentation edition first.');return
        self.status.setText('Loading the complete '+docset['name']+' collection…');self.worker('examples',lambda:collection_examples(docset,online=online))
    def load_url(self):
        if self.busy:return
        url,ok=QInputDialog.getText(self,'Load source examples','Public HTTPS documentation, source file or repository URL:')
        if ok and url.strip():
            language=self.language_box.currentText();online=self.online.isChecked();self.worker('examples',lambda:url_examples(url.strip(),language,online=online))
    def show_examples(self,examples,status):
        self.examples=examples;self.example_box.clear();self.example_box.addItems([str(i+1)+'. '+e['language']+' · '+e['title'] for i,e in enumerate(examples)])
        self.export_button.setEnabled(bool(examples));self.status.setText(status)
        if examples:
            index=next((i for i,e in enumerate(examples) if e['language']==self.language_box.currentText()),0);self.example_box.setCurrentIndex(index);self.select_example(index)
        else:self.status.setText(status+' No readable code blocks found. Your code is retained.')
    def select_example(self,index=None):
        index=self.example_box.currentIndex() if index is None else index
        if index<0 or index>=len(self.examples) or not self.can_replace():return
        example=self.examples[index];self.set_code(example['code'],example['language'],'Source example · '+example['url']);self.editor_dirty=True
        self.tabs.setCurrentIndex(0);self.workbench_tabs.setCurrentIndex(0)
        self.set_guidance('Source: '+example['url']+'\n\n'+example.get('licence','Check source terms')+'\n\n'+example.get('attribution','')+'\n\nCheck the imports, context and dependencies before adapting this reference example. Save your version and test its expected output.')
    def save_examples(self):
        if not self.examples:return
        path,_=QFileDialog.getSaveFileName(self,'Save source examples','OG Companion - Source Examples.json','JSON (*.json)')
        if path:
            try:Path(path).write_text(json.dumps({'examples':self.examples},ensure_ascii=False,indent=2),encoding='utf-8')
            except OSError as error:self.status.setText('Could not save: '+str(error))
            else:self.status.setText('Saved all '+str(len(self.examples))+' source blocks with references.')
    def refresh_sources(self):
        if self.busy:return
        if not self.online.isChecked():self.status.setText('Enable online sources to refresh the catalogue.');return
        self.worker('docsets',lambda:documentation_catalogue(online=True))
    def refresh_models(self):
        if self.models_loading or self.disposed:return
        self.models_loading=True;self.models_button.setEnabled(False);self.model_note.setText('Finding local models… You can keep typing and browsing.');endpoints=list(self.extra_endpoints)
        def run():
            try:self.results.put(('models',True,discover_models(endpoints)))
            except Exception as error:self.results.put(('models',False,str(error)))
        threading.Thread(target=run,daemon=True).start()
    def add_model_endpoint(self):
        endpoint,ok=QInputDialog.getText(self,'Local service URL','Localhost base URL, for example http://localhost:1234:')
        if not ok or not endpoint.strip():return
        try:endpoint=local_endpoint(endpoint)
        except ValueError as error:self.status.setText(str(error));return
        if endpoint not in self.extra_endpoints:self.extra_endpoints.append(endpoint)
        try:self.settings_path.parent.mkdir(parents=True,exist_ok=True);self.settings_path.write_text(json.dumps({'endpoints':self.extra_endpoints}),encoding='utf-8')
        except OSError as error:self.status.setText('Service URL could not be saved: '+str(error))
        self.refresh_models()
    def connect_model(self):
        index=self.model_table.currentRow()
        if index<0 or index>=len(self.model_records):self.status.setText('Select a model from the table first.');return
        selected=dict(self.model_records[index]);self.connect_button.setEnabled(False);self.model_note.setText('Connecting '+selected['name']+'…')
        def run():
            try:self.results.put(('connected',True,connect_local_model(selected)))
            except Exception as error:self.results.put(('connected',False,str(error)))
        threading.Thread(target=run,daemon=True).start()
    def add_service_token(self):
        endpoint,ok=QInputDialog.getText(self,'Protected local service','Localhost service base URL:')
        if not ok:return
        try:endpoint=local_endpoint(endpoint)
        except ValueError as error:self.status.setText(str(error));return
        token,ok=QInputDialog.getText(self,'Service token','Token for this session only. Leave blank to remove it:',QLineEdit.EchoMode.Password)
        if not ok:return
        set_service_token(endpoint,token)
        if endpoint not in self.extra_endpoints:self.extra_endpoints.append(endpoint)
        self.refresh_models()
    def disconnect_model(self):
        self.connected_model=None;self.connection_label.setText('Reference code available · no model connected');self.model_note.setText('Disconnected. Library examples and starters remain available.')
    def generate(self,expand=False):
        if self.busy:return
        description=self.description.toPlainText().strip();language=self.language_box.currentText().strip();existing=self.output.toPlainText()
        if expand and not existing.strip():self.status.setText('Build or load code before expanding it.');return
        if existing.strip() and language!=self.editor_language:self.status.setText('Your code is '+self.editor_language+'. Choose that language to update it, or save and clear it.');return
        if expand and not description:description=self.previous_description or 'Add one useful working feature while preserving this program.'
        if not description or not language:self.status.setText('Describe what you want to build and choose a language.');self.description.setFocus();return
        entries=task_libraries(description,language);self.set_guidance(task_guidance(description,language,entries))
        if not existing.strip():self.show_results(entries,'Finding a starting point…')
        program_mode=self.mode_box.currentText()=='Starter program';blueprint=starter_program(description,language) if program_mode and not existing.strip() else None
        if blueprint:
            self.set_code(blueprint[0],language,'Built-in starter program · '+blueprint[1]);self.editor_dirty=True;self.previous_description=description
            self.status.setText('Starter code ready. How to build it explains the approach and next steps.');self.workbench_tabs.setCurrentIndex(0);return
        if not self.connected_model:
            if not existing.strip() and entries and entries[0].get('snippet'):
                self.set_code(entries[0]['snippet'],language,'Reference snippet · '+entries[0]['name']);self.editor_dirty=True;self.status.setText('Reference snippet ready. Connect a model for a full custom program.');return
            if existing.strip():self.status.setText('Connect a local model to update or expand your code. Your edits are retained.');return
            self.reference_starter(description,language);return
        connection=dict(self.connected_model);entry=dict(self.selected_library) if self.selected_library else None
        if entry and self.examples:entry['reference_examples']=[{'code':e['code'][:5000],'source':e['url'],'language':e['language']} for e in self.examples if e['language']==language][:3]
        self.generation_baseline=existing;round_number=self.expansion_round+1 if existing.strip() else 0;previous=self.previous_description;self.status.setText('Your local model is building or updating the code…')
        def run():
            code=generate_snippet(description,language,connection.get('inference_name') or connection['name'],entry,existing,program_mode=program_mode,
                expansion_round=round_number,previous_description=previous,additional_feature=expand,endpoint=connection['endpoint'],provider=connection['provider'])
            return code,language,description,round_number
        self.worker('generate',run)
    def reference_starter(self,description,language):
        terms=task_terms(description);online=self.online.isChecked();docset=self.docset_labels.get(self.docset_box.currentText());matching=next((d for d in self.docsets if d['name'].casefold() in terms),None)
        self.status.setText('Looking for matching documentation examples…')
        def run():
            if matching:
                entry=package_result(matching['name'],language,'Documentation collection','Published examples.',matching.get('version') or 'Current','https://devdocs.io/'+matching['slug'],'See source documentation')
                examples,status=collection_examples(matching,online=online);return [entry],examples,status
            if docset:
                rows,status=documentation_search(docset,' '.join(sorted(terms)),online=online,language=language)
                for entry in rows[:5]:
                    examples,result=library_examples(entry,online=online)
                    if examples:return rows,examples,result
            return [],[],'No source example found for these keywords. Browse an exact library or connect a model for custom code.'
        self.worker('task_reference',run)
    def can_replace(self):
        return not self.editor_dirty or QMessageBox.question(self,'Keep your edits?','Replace the code in your workbench? Save or copy it first to keep it.',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)==QMessageBox.StandardButton.Yes
    def set_code(self,code,language,origin,*,keep_undo=False,reset_history=True):
        if keep_undo:self.history.append((self.output.toPlainText(),self.editor_language,self.code_origin.text()))
        elif reset_history:self.history=[];self.expansion_round=0;self.previous_description=''
        self.setting_code=True;self.output.setPlainText(code);self.setting_code=False;self.editor_dirty=False;self.editor_language=language;self.code_origin.setText(origin+' · '+language)
    def code_modified(self):
        if not self.setting_code:self.editor_dirty=True
    def poll(self):
        if self.disposed:return
        while True:
            try:kind,success,value=self.results.get_nowait()
            except queue.Empty:break
            if kind=='models':
                self.models_loading=False;self.models_button.setEnabled(True)
                if success:
                    self.model_records=value;self.model_table.setRowCount(len(value))
                    for i,record in enumerate(value):
                        state=record.get('kind','llm') if record.get('kind','llm')!='llm' else ('Loaded' if record.get('loaded') else 'Available')
                        for j,text in enumerate((record['name'],record['provider'],record['endpoint'],state)):self.model_table.setItem(i,j,QTableWidgetItem(text))
                    if value:self.model_table.selectRow(0)
                    self.model_note.setText(str(len(value))+' models found. Select one, then Connect selected model. Nothing connects automatically.' if value else 'No reachable service. Start Ollama or LM Studio, or add its localhost URL. Library examples still work.')
                else:self.model_note.setText('Discovery failed: '+str(value))
                continue
            if kind=='connected':
                self.connect_button.setEnabled(True)
                if success:self.connected_model=value;self.connection_label.setText(value['name']+' · connected');self.model_note.setText('Connected to '+value['name']+' at '+value['endpoint']+'. Return to Build code to use it.')
                else:self.model_note.setText('Could not connect: '+str(value))
                continue
            if kind=='details':
                token,result=value
                if token==self.selection_token and success:self.selected_library=result;self.show_details(result)
                continue
            if kind=='completed':
                epoch,kind,success,value=value
                if epoch!=self.work_epoch:continue
                self.active_work=None;self.set_busy(False)
            if not success:self.status.setText('Could not complete: '+str(value));continue
            if kind=='search':self.show_results(*value)
            elif kind=='examples':self.show_examples(*value)
            elif kind=='task_reference':self.show_results(value[0],value[2]);self.show_examples(value[1],value[2])
            elif kind=='docsets':
                self.docsets=value;self.docset_labels={d['name']+' '+str(d.get('version') or '')+' ['+d['slug']+']':d for d in value};self.docset_box.clear();self.docset_box.addItems(list(self.docset_labels));self.choose_default_docset();self.status.setText(str(len(value))+' editions available.')
            elif kind=='generate':
                if self.output.toPlainText()!=self.generation_baseline and QMessageBox.question(self,'Newer changes','Your code changed while the model was working. Replace those newer edits?',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:self.status.setText('Your newer edits are retained.');continue
                self.set_code(value[0],value[1],'Local model suggestion',keep_undo=True);self.editor_dirty=True;self.previous_description=value[2];self.expansion_round=value[3];self.workbench_tabs.setCurrentIndex(0)
                self.status.setText('Code ready. Edit it, save it and test the result. Change the description to request the next addition.')
    def open_docs(self):
        url=self.selected_library.get('docs','') if self.selected_library else ''
        if url.startswith(('https://','http://')):webbrowser.open(url)
    def copy_install(self):
        if self.selected_library:application().clipboard().setText(self.selected_library.get('install',''));self.status.setText('Installation guidance copied. No packages installed.')
    def copy(self):application().clipboard().setText(self.output.toPlainText());self.status.setText('Current code copied, including your edits.')
    def save(self):
        code=self.output.toPlainText()
        if not code.strip():self.status.setText('Build or load code before saving.');return
        ext=EXTENSIONS.get(self.editor_language,'.txt');path,_=QFileDialog.getSaveFileName(self,'Save code','og-starter'+ext,'Source (*'+ext+');;All files (*)')
        if path:
            try:Path(path).write_text(code.rstrip()+'\n',encoding='utf-8')
            except OSError as error:self.status.setText('Could not save: '+str(error))
            else:self.editor_dirty=False;self.status.setText('Your code has been saved.')
    def closeEvent(self,event):
        if not self.disposed and self.editor_dirty and QMessageBox.question(self,'Unsaved code','Close without saving your workbench edits?',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:event.ignore();return
        if not self.disposed and self.initial_placement_done:
            try:
                self.placement_path.parent.mkdir(parents=True,exist_ok=True)
                self.placement_path.write_text(json.dumps({'screen':self.screen().name()}),encoding='utf-8')
            except OSError:pass
        self.disposed=True;self.timer.stop();event.accept()
    def dispose(self):self.disposed=True;self.timer.stop();self.close();self.deleteLater();application().processEvents()

def check_installation(report_path,*,online=False):
    report={};window=None
    try:
        window=OGCompanion(discover_models=False);window.description.setPlainText('Read CSV and save JSON');window.generate_button.click();code=window.output.toPlainText();ast.parse(code)
        report.update(application_title=window.windowTitle(),catalogue_entries=len(load_catalogue()),documentation_editions=len(window.docsets),tabs=[window.tabs.tabText(i) for i in range(window.tabs.count())],logo_loaded=not window.surface.logo.isNull(),starter_program_loaded='def valid_row' in code,runtime_location=str(BASE))
        window.clear_search_button.click();report['clear_search_preserves_program']=window.output.toPlainText()==code and not window.entries
        window.set_code(code+'\n# Undo check\n','Python','Check',keep_undo=True);window.undo_button.click();report['undo_restores_program']=window.output.toPlainText()==code
        window.set_code('','Python','Check');window.description.setPlainText('cybersecurity, file libraries, security considerations');window.generate_button.click()
        report['cybersecurity_starter_loaded']='def file_hash' in window.output.toPlainText() and 'Hashes detect changes' in window.guidance.toPlainText()
        report['passed']=all(report[k] for k in ('logo_loaded','starter_program_loaded','clear_search_preserves_program','undo_restores_program','cybersecurity_starter_loaded')) and len(report['tabs'])==3
        if online:
            from og_companion_sources import fetch_text,extract_examples
            text,url,_=fetch_text('https://documents.devdocs.io/python~3.14/library/csv.html');report['online_document_examples']=len(extract_examples(text,url,'Python'));report['passed']=report['passed'] and report['online_document_examples']>0
    except Exception as error:report.update(passed=False,error=str(error))
    finally:
        if window:window.dispose()
    Path(report_path).write_text(json.dumps(report,indent=2),encoding='utf-8');return 0 if report['passed'] else 1
if __name__=='__main__':
    if len(sys.argv)==3 and sys.argv[1] in ('--check-installation','--check-online-sources'):raise SystemExit(check_installation(sys.argv[2],online=sys.argv[1]=='--check-online-sources'))
    window=OGCompanion();window.show();raise SystemExit(application().exec())
