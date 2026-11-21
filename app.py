import os
import sys
import threading
import time
from pathlib import Path
from PySide6.QtCore import Qt, QRectF, QPointF, QObject, QRunnable, QThreadPool, Signal, Slot, QTimer, QUrl
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPainter, QPainterPath, QPen, QImage, QShortcut, QKeySequence, QDesktopServices
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QFrame,QLabel,QPushButton,QSlider,QHBoxLayout,QVBoxLayout,QFileDialog,QMessageBox,QProgressBar,QSizePolicy,QComboBox,QButtonGroup)
import engine as eng
import inspection as scope
from grade_ui import Controls
from release_info import PRODUCT,SUPPORT_URL,VERSION
from startup_notices import StartupNotices

NAME=f'{PRODUCT} V{VERSION}'
WEBSITE='https://y-g-jiang.github.io'
SUPPORT=SUPPORT_URL
INK='#eae8e3'; MUTE='#aaa9a5'; ACCENT='#eb674f'
CSS='''
QWidget {background:#242525;color:#ebeae5;font-size:14px;} QFrame#top {background:#242525;border-bottom:1px solid #383939;}
QWidget#side {background:#292a2a;border-left:1px solid #383939;} QWidget#side QLabel,QWidget#side QWidget#plain {background:transparent;}
QLabel#micro {color:#aaa9a5;font-size:11px;font-weight:600;} QLabel#brand {font-size:18px;font-weight:650;} QLabel#title {font-size:23px;font-weight:650;}
QPushButton {background:#363838;border:1px solid #464848;border-radius:7px;padding:8px 15px;font-weight:500;} QPushButton:hover {background:#454747;} QPushButton:pressed {background:#292b2b;} QPushButton:disabled {color:#858787;background:#303232;border-color:#3b3d3d;}
QPushButton#primary {background:#e86751;color:#181816;border:0;font-weight:700;padding:12px;} QPushButton#primary:hover {background:#f37d66;} QPushButton#primary:disabled {background:#4b4340;color:#a39892;}
QPushButton#textbtn {background:transparent;border:none;color:#bcbbb6;padding:5px;} QPushButton#textbtn:hover {color:#ffffff;} QSlider::groove:horizontal {height:4px;border-radius:2px;background:#565857;}
QSlider::handle:horizontal {width:15px;margin:-6px 0;background:#f3f1eb;border:1px solid #cdccc6;border-radius:8px;} QSlider:focus {outline:1px solid #b29382;}
QProgressBar {max-height:4px;background:#454646;border:0;} QProgressBar::chunk {background:#eb674f;}
QTabWidget::pane {border:none;} QTabBar::tab {background:#303432;color:#b4bab6;padding:6px 11px;} QTabBar::tab:selected {background:#374943;color:#b6e6d6;} QScrollArea {border:none;} QDoubleSpinBox {padding:3px 2px;background:#303738;color:#eee;border:1px solid #49514f;}
QFrame#strip {background:#202627;border:0;} QFrame#strip QLabel {background:transparent;color:#8ed4c4;font-size:11px;font-weight:600;} QComboBox {background:#303738;border:1px solid #4a5051;border-radius:5px;padding:4px 8px;min-width:84px;}
QFrame#selector {background:#191a1a;border:1px solid #444444;border-radius:6px;} QPushButton#look {padding:6px 13px;color:#aaa9a5;background:transparent;border:1px solid transparent;border-radius:3px;} QPushButton#look:hover {color:#eee9e2;background:#333333;} QPushButton#look:checked {color:#fff0e5;background:#492d2b;border:1px solid #c55e50;} QPushButton#look:focus {border:1px solid #e2bfa9;}
QPushButton#primary {background:#ba3c34;color:#fff9f3;border:1px solid #ce5249;} QPushButton#primary:hover {background:#cb463c;} QPushButton#primary:disabled {background:#403331;color:#ab9995;}
QPushButton#website {background:transparent;border:none;padding:0;color:#f07768;font-size:12px;text-align:left;} QPushButton#website:hover {color:#ffac9c;text-decoration:underline;} QLabel#byline {font-size:12px;color:#aaa9a5;} QToolTip {background:#f2f0eb;color:#191a19;padding:5px;border:0;}'''

def label(text,style=None):
    item=QLabel(text)
    if style:item.setObjectName(style)
    item.setTextFormat(Qt.PlainText);return item

def button(text,slot,name=''):
    item=QPushButton(text);item.setObjectName(name);item.clicked.connect(slot);item.setCursor(Qt.PointingHandCursor);return item

def rgb_image(arr):return QImage(arr.data,arr.shape[1],arr.shape[0],arr.strides[0],QImage.Format_RGB888).copy()

class Canvas(QWidget):
    def __init__(self,parent):
        super().__init__();self.owner=parent;self.picture=QImage();self.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Expanding);self.setMinimumSize(260,220)
        self.layer=QImage();self.mask_pair=None;self.mask_alpha=0.;self.split=.5;self.anchor=(.5,.5);self.frame=QRectF();self.matrix=QRectF();self.dragging=False;self.hover_cell=None;self.setMouseTracking(True);self.setFocusPolicy(Qt.ClickFocus)

        self.compare_image=QImage();self.compare_split=.5

    def show_array(self,arr,source=None):
        self.picture=rgb_image(arr);self.compare_image=rgb_image(source) if self.owner.comparing and source is not None else QImage();self.update()

    def divider(self):return self.compare_split if self.owner.comparing else self.split
    def cycling(self):return self.mask_pair is not None and not self.owner.comparing and self.owner.motion.isActive()
    def parked(self):return not self.owner.comparing and self.split==0
    def edge_tab(self):return QRectF(self.frame.left()-21,self.frame.center().y()-15,18,30)
    def at_divider(self,pos):
        if self.parked():return self.edge_tab().adjusted(-3,-6,6,6).contains(pos)
        return self.frame.contains(pos) and abs(pos.x()-self.frame.left()-self.divider()*self.frame.width())<=12
    def has_overlay(self):return not self.compare_image.isNull() if self.owner.comparing else bool(self.mask_pair) or not self.layer.isNull()

    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);p.fillRect(self.rect(),QColor('#181a1b'))
        box=QRectF(self.rect()).adjusted(24,24,-24,-24)
        if not self.picture.isNull():
            scale=min(box.width()/self.picture.width(),box.height()/self.picture.height());width,height=self.picture.width()*scale,self.picture.height()*scale
            frame=QRectF((self.width()-width)/2,(self.height()-height)/2,width,height);self.frame=frame;p.setRenderHint(QPainter.SmoothPixmapTransform);p.drawImage(frame,self.picture)
            rim=frame.adjusted(-5,-5,5,5);p.setPen(QPen(QColor('#777672'),1))
            for point,dx,dy in ((rim.topLeft(),1,1),(rim.topRight(),-1,1),(rim.bottomLeft(),1,-1),(rim.bottomRight(),-1,-1)):
                p.drawLine(point,point+QPointF(dx*9,0));p.drawLine(point,point+QPointF(0,dy*9))
            if self.cycling():
                first,second=self.mask_pair;p.drawImage(frame,first);p.setOpacity(self.mask_alpha);p.drawImage(frame,second)
            elif self.parked():
                tab=self.edge_tab();point=tab.center();p.setBrush(QColor('#213735'));p.setPen(QPen(QColor('#a6d9cc'),1));p.drawRoundedRect(tab,7,7)
                p.drawLine(point+QPointF(-2,-4),point+QPointF(2,0));p.drawLine(point+QPointF(2,0),point+QPointF(-2,4))
            elif self.has_overlay():self.draw_scope(p,frame)
            return
        center=box.center();cx,cy=center.x(),center.y()-55;card=QRectF(cx-77,cy-49,154,94)
        p.save();p.translate(cx,cy);p.rotate(-9);p.setPen(QPen(QColor('#555754'),1.3));p.setBrush(QColor('#232625'));p.drawRoundedRect(QRectF(-90,-48,151,92),7,7);p.restore()
        p.setPen(QPen(QColor('#666761'),1.4));p.setBrush(QColor('#303330'));p.drawRoundedRect(card,7,7);p.setPen(Qt.NoPen);p.setBrush(QColor(ACCENT));p.drawEllipse(QPointF(cx+32,cy-21),8,8)
        path=QPainterPath(QPointF(cx-68,cy+32));path.cubicTo(cx-35,cy+17,cx-29,cy-23,cx-4,cy+2);path.cubicTo(cx+21,cy+27,cx+35,cy-8,cx+68,cy+9);p.setBrush(Qt.NoBrush);p.setPen(QPen(QColor('#b0b1a4'),2));p.drawPath(path)
        font=p.font();font.setPixelSize(24);font.setWeight(QFont.DemiBold);p.setFont(font);p.setPen(QColor(INK));p.drawText(QRectF(0,cy+77,self.width(),36),Qt.AlignCenter,'拖入一张照片')
        font.setPixelSize(13);font.setWeight(QFont.Normal);p.setFont(font);p.setPen(QColor(MUTE));p.drawText(QRectF(0,cy+121,self.width(),25),Qt.AlignCenter,'或点此打开  ·  RAW / JPEG / PNG / TIFF')

    def draw_scope(self,p,frame):
        cut=frame.left()+frame.width()*self.divider();area=QRectF(frame.left(),frame.top(),cut-frame.left(),frame.height());mode=self.owner.mode()
        p.save();p.setClipRect(area)
        if self.owner.comparing:p.drawImage(frame,self.compare_image)
        elif mode=='routing':
            p.fillRect(area,QColor('#162023'));size=max(1,min(area.width()-24,area.height()-76));center=area.center();self.matrix=QRectF(center.x()-size/2,center.y()-size/2,size,size)
            p.setRenderHint(QPainter.SmoothPixmapTransform,False);p.drawImage(self.matrix,self.layer);p.setPen(QPen(QColor(24,35,38,130),1))
            for grid in range(1,16):
                value=grid*size/16;p.drawLine(self.matrix.topLeft()+QPointF(value,0),self.matrix.bottomLeft()+QPointF(value,0));p.drawLine(self.matrix.topLeft()+QPointF(0,value),self.matrix.topRight()+QPointF(0,value))
            p.setPen(QColor('#b4cfc8'));text='16 × 16'
            if self.hover_cell:
                row,col=self.hover_cell;weights=self.owner.cache[4][f'routing_{self.owner.variant_index()}'][0];text=f'{row+1:02d} → {col+1:02d}   {weights[row,col]:.1%}'
                p.setPen(QPen(QColor('#fff8de'),2));p.drawRect(QRectF(self.matrix.left()+col*size/16,self.matrix.top()+row*size/16,size/16,size/16))
            p.drawText(QRectF(area.left(),self.matrix.bottom()+3,area.width(),23),Qt.AlignCenter,text)
        else:p.drawImage(frame,self.layer)
        p.restore();p.setPen(QPen(QColor('#ccf6ec'),1));p.drawLine(QPointF(cut,frame.top()),QPointF(cut,frame.bottom()))
        center=QPointF(cut,frame.center().y());p.setBrush(QColor('#213735'));p.setPen(QPen(QColor('#a6d9cc'),1));p.drawRoundedRect(QRectF(cut-9,center.y()-14,18,28),8,8)
        for step in (-2,2):p.drawLine(center+QPointF(step,-4),center+QPointF(step,4))
        if mode=='features' and not self.owner.comparing and not self.mask_pair:
            pos=QPointF(frame.left()+self.anchor[0]*frame.width(),frame.top()+self.anchor[1]*frame.height());p.setBrush(Qt.NoBrush);p.setPen(QPen(QColor('#162423'),4));p.drawEllipse(pos,7,7);p.setPen(QPen(QColor('#c2ffe8'),1.5));p.drawEllipse(pos,7,7)

    def mousePressEvent(self,event):
        if event.button()==Qt.LeftButton and not self.cycling() and not self.picture.isNull() and (self.parked() or self.has_overlay()):
            pos=event.position()
            if self.at_divider(pos):self.dragging=True;self.setCursor(Qt.SplitHCursor);event.accept();return
            if not self.parked() and self.frame.contains(pos) and self.owner.mode()=='features' and not self.owner.comparing and not self.mask_pair:
                self.anchor=((pos.x()-self.frame.left())/self.frame.width(),(pos.y()-self.frame.top())/self.frame.height());self.owner.refresh_layer();event.accept();return
        super().mousePressEvent(event)

    def mouseMoveEvent(self,event):
        if self.picture.isNull() or (self.cycling() and not self.dragging) or not (self.dragging or self.parked() or self.has_overlay()):self.unsetCursor();return
        pos=event.position();frame=self.frame
        if self.dragging:
            distance=pos.x()-frame.left();fraction=min(.92,distance/max(1,frame.width()))
            if self.owner.comparing:self.compare_split=max(.08,fraction)
            else:
                parked=self.parked();self.split=0. if distance<=3 else fraction
                if self.parked()!=parked:self.hover_cell=None;self.owner.refresh_layer()
            self.update();return
        self.setCursor(Qt.SplitHCursor if self.at_divider(pos) else Qt.CrossCursor if not self.parked() and not self.owner.comparing and not self.mask_pair and self.owner.mode()=='features' and frame.contains(pos) else Qt.ArrowCursor)
        cell=None
        if not self.parked() and not self.owner.comparing and not self.mask_pair and self.owner.mode()=='routing' and self.matrix.contains(pos):cell=tuple(max(0,min(15,int(value*16))) for value in ((pos.y()-self.matrix.top())/self.matrix.height(),(pos.x()-self.matrix.left())/self.matrix.width()))
        if cell!=self.hover_cell:self.hover_cell=cell;self.update()

    def leaveEvent(self,event):self.hover_cell=None;self.update();super().leaveEvent(event)

    def mouseReleaseEvent(self,event):
        if self.dragging:self.dragging=False;event.accept();return
        if self.picture.isNull() and event.button()==Qt.LeftButton:self.owner.pick()

class Signals(QObject):
    done=Signal(object);failed=Signal(str);progress=Signal(int,int)

class Job(QRunnable):
    def __init__(self,fn):super().__init__();self.fn=fn;self.signal=Signals()
    def run(self):
        try:self.signal.done.emit(self.fn(self.signal.progress.emit))
        except Exception as exc:self.signal.failed.emit(str(exc) or type(exc).__name__)

class Window(QMainWindow):
    def __init__(self):
        super().__init__();self.setWindowTitle(NAME);self.setMinimumSize(810,555);self.resize(1170,760);self.setAcceptDrops(True)
        self.engine=eng.Engine();self.pool=QThreadPool(self);self.pool.setMaxThreadCount(1);self.photo=None;self.intent=None;self.active=None;self.version=0;self.cache=None;self.comparing=False;self.exporting=False;self.abort=threading.Event();self.directory=None;self.last=None;self.closing=False
        self.timer=QTimer(self);self.timer.setTimerType(Qt.PreciseTimer);self.timer.setSingleShot(True);self.timer.timeout.connect(self.request_preview)
        self.adjusting=False;self.options=None;self.scan=None;self.output=None;self.pending=None;self.preview_abort=threading.Event();self.mask_key=None;self.mask_step=-1
        self.motion=QTimer(self);self.motion.setInterval(33);self.motion.timeout.connect(self.mask_tick)
        self.load_abort=threading.Event()
        root=QWidget();self.setCentralWidget(root);v=QVBoxLayout(root);v.setContentsMargins(0,0,0,0);v.setSpacing(0)
        top=QFrame();top.setObjectName('top');bar=QHBoxLayout(top);bar.setContentsMargins(18,9,18,9);brand=QVBoxLayout();brand.setSpacing(0);brand.addWidget(label(NAME,'brand'));byline=QHBoxLayout();byline.addWidget(label('by 姜尧耕','byline'));self.website=button('y-g-jiang.github.io',lambda:QDesktopServices.openUrl(QUrl(WEBSITE)),'website');byline.addWidget(self.website);byline.addStretch();brand.addLayout(byline);bar.addLayout(brand);bar.addStretch()
        byline.setSpacing(8);self.engines={self.engine.profile:self.engine};self.look_frames={};self.looks={};self.look_group=QButtonGroup(self)
        selector=QFrame();selector.setObjectName('selector');row=QHBoxLayout(selector);row.setContentsMargins(3,3,3,3);row.setSpacing(2)
        for key,name in eng.PROFILES.items():
            look=QPushButton(name);look.setObjectName('look');look.setAccessibleName(name);look.setCheckable(True);look.setCursor(Qt.PointingHandCursor);self.look_group.addButton(look);look.setChecked(key==self.engine.profile);look.clicked.connect(lambda checked,profile=key:self.select_profile(profile));row.addWidget(look);self.looks[key]=look
        bar.addWidget(selector);bar.addSpacing(6);self.support=button('支持作者',lambda:QDesktopServices.openUrl(QUrl(SUPPORT)));bar.addWidget(self.support)
        self.open_btn=button('打开照片…',self.pick);bar.addWidget(self.open_btn);v.addWidget(top)
        body=QHBoxLayout();body.setSpacing(0);v.addLayout(body,1);workspace=QWidget();wl=QVBoxLayout(workspace);wl.setContentsMargins(0,0,0,0);wl.setSpacing(0);body.addWidget(workspace,1)
        header=QHBoxLayout();header.setContentsMargins(24,8,18,8);self.file_label=label('照片预览');self.file_label.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred);header.addWidget(self.file_label,1);self.compare=QPushButton('原图对比');self.compare.setCursor(Qt.PointingHandCursor);self.compare.setCheckable(True);self.compare.setFixedWidth(112);self.compare.setToolTip('切换左右对比（空格）');self.compare.toggled.connect(self.set_comparison);header.addWidget(self.compare);wl.addLayout(header)
        self.resolution=QComboBox();self.resolution.setAccessibleName('预览分辨率');self.resolution.setToolTip('预览长边，不改变全图导出尺寸。')
        for edge in eng.PREVIEW_EDGES:self.resolution.addItem(f'{edge} px',edge)
        self.resolution.setCurrentIndex(self.resolution.findData(512));header.insertWidget(1,label('预览','micro'));header.insertWidget(2,self.resolution);self.resolution.currentIndexChanged.connect(self.request_preview)
        self.strip=QFrame();self.strip.setObjectName('strip');strip=QHBoxLayout(self.strip);strip.setContentsMargins(16,5,14,5);strip.setSpacing(8);strip.addWidget(label('显影透视'));self.layers=QComboBox();self.layers.setAccessibleName('观察层');self.variants=QComboBox();self.variants.setAccessibleName('观察通道');strip.addWidget(self.layers);strip.addWidget(self.variants);strip.addStretch();self.scope_state=label('');strip.addWidget(self.scope_state);wl.addWidget(self.strip)
        for key,(name,_,_) in scope.MODES.items():self.layers.addItem(name,key)
        self.scope_state.setMinimumWidth(self.scope_state.fontMetrics().horizontalAdvance('左 · 观察    /    右 · 成片')+8);self.scope_state.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
        self.canvas=Canvas(self);wl.addWidget(self.canvas,1);self.layer_key=None
        self.configure_layer();self.layers.currentIndexChanged.connect(self.configure_layer);self.variants.currentIndexChanged.connect(self.refresh_layer)
        side=QWidget();side.setObjectName('side');side.setFixedWidth(285);body.addWidget(side);panel=QVBoxLayout(side);panel.setContentsMargins(18,19,18,14);panel.setSpacing(8);panel.addWidget(label('DARKROOM    /    02','micro'));panel.addWidget(label('影调','title'));self.controls=Controls();panel.addWidget(self.controls,1);self.controls.changed.connect(self.edited);self.controls.released.connect(self.release)
        self.reset=button('重置全部调节',self.reset_tone,'textbtn');panel.addWidget(self.reset,0,Qt.AlignLeft);self.folder=button('保存到：原片旁  ›',self.choose_dir,'textbtn');panel.addWidget(self.folder,0,Qt.AlignLeft)
        self.controls.pressed.connect(self.pause_edits);self.save=button('处理全图',self.start_export,'primary');panel.addWidget(self.save);foot=label('原尺寸  ·  16 位 TIFF + JPEG 80','micro');foot.setAlignment(Qt.AlignCenter);panel.addWidget(foot)
        self.progress=QProgressBar();self.progress.setTextVisible(False);self.progress.hide();v.addWidget(self.progress);status=QHBoxLayout();status.setContentsMargins(22,6,16,6);self.message=label('就绪','micro');self.message.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred);status.addWidget(self.message,1);self.reveal=button('打开输出文件夹',self.open_folder,'textbtn');status.addWidget(self.reveal);self.reveal.hide();v.addLayout(status);self.toggle()
        self.feedback=label('问题反馈： QQ 1025168246','micro');self.feedback.setTextInteractionFlags(Qt.TextSelectableByMouse);status.insertWidget(0,self.feedback);status.setSpacing(16)
        self.keys=[]
        for sequence,fn in ((QKeySequence.Open,self.pick),(QKeySequence.Save,self.start_export)):
            sc=QShortcut(QKeySequence(sequence),self);sc.activated.connect(fn);self.keys.append(sc)
        shortcut=QShortcut(QKeySequence(Qt.Key_Space),self);shortcut.setAutoRepeat(False);shortcut.activated.connect(self.compare.click);self.keys.append(shortcut)

    def select_profile(self,key):
        if self.exporting or key==self.engine.profile:return
        if self.photo:self.look_frames[self.engine.profile]=(self.cache,self.output,self.scan)
        self.stop_masks()
        if key not in self.engines:self.engines[key]=eng.Engine(key)
        self.engine=self.engines[key];self.cache,self.output,self.scan=self.look_frames.get(key,(None,None,None));self.looks[key].setChecked(True)
        if not self.photo:return
        self.invalidate_preview()
        self.timer.stop();self.adjusting=False;self.controls.deferred=False;self.layer_key=None;self.canvas.hover_cell=None;self.paint_live();self.notice('正在显影  ·  '+eng.PROFILES[key]);self.request_preview()

    def params(self):return self.controls.settings()
    def preview_key(self):return (self.params(),self.resolution.currentData())
    def ready(self):return self.output is not None and self.output[:2]==self.preview_key()
    def invalidate_preview(self):
        self.preview_abort.set();self.pending=None;self.version+=1;self.intent=None
        if self.options is not None:self.options.terminate=True;self.options=None
    def stop_masks(self):
        self.motion.stop();self.mask_key=None;self.mask_step=-1;self.canvas.mask_pair=None;self.canvas.update()
    def start_masks(self):
        key=(id(self.scan),self.canvas.anchor)
        if not self.motion.isActive():self.mask_start=time.monotonic();self.motion.start()
        if key!=self.mask_key:
            self.mask_key=key;self.mask_step=-1;self.canvas.mask_pair=None;self.canvas.hover_cell=None;self.canvas.layer=QImage();self.layer_key=None;self.mask_tick()
    def mask_tick(self):
        phase=(time.monotonic()-self.mask_start)/.96;step=int(phase);index=step%len(scope.MASK_CYCLE)
        def frame(number):
            mode,variant=scope.MASK_CYCLE[number%len(scope.MASK_CYCLE)];return rgb_image(scope.draw_layer(self.photo,self.scan,mode,variant,self.canvas.anchor))
        if self.mask_step!=step:
            pair=self.canvas.mask_pair;first=pair[1] if pair and self.mask_step+1==step else frame(index)
            self.canvas.mask_pair=(first,frame(index+1));self.mask_step=step
        blend=min(1.,max(0.,(phase-step-.20)/.8));self.canvas.mask_alpha=blend*blend*(3-2*blend)
        mode,variant=scope.MASK_CYCLE[(index+(blend>=.5))%len(scope.MASK_CYCLE)];name=scope.MODES[mode][1][variant].split(' · ')[0]
        self.scope_state.setText(('显影中' if self.scan[0]==self.params() else '上一帧')+' · '+name);self.canvas.update()
    def mode(self):return self.layers.currentData()
    def variant_index(self):return max(0,self.variants.currentIndex())
    def configure_layer(self,*args):
        _,variants,_=scope.MODES[self.mode()];self.variants.blockSignals(True);self.variants.clear();self.variants.addItems(variants);self.variants.setCurrentIndex(3 if self.mode()=='features' else 0);self.variants.blockSignals(False);self.variants.setVisible(bool(variants));self.canvas.hover_cell=None;self.refresh_layer()
    def refresh_layer(self,*args):
        if self.comparing:
            self.scope_state.setText('等待成片' if self.canvas.compare_image.isNull() else '左 · 原图    /    右 · 成片');return
        if not self.adjusting and self.pending and self.scan and not self.ready() and not self.exporting:
            self.start_masks();return
        if self.canvas.parked():
            if self.mask_key:self.stop_masks()
            self.layer_key=None;self.canvas.layer=QImage();self.scope_state.setText('成片');self.canvas.setToolTip('向右拖动，查看显影透视。');return
        if self.adjusting:return
        if self.mask_key:self.stop_masks()
        if not self.cache or self.cache[0]!=self.params() or self.cache[4] is None:
            self.layer_key=None;self.canvas.layer=QImage();self.canvas.unsetCursor();self.canvas.update()
            self.scope_state.setText('')
            return
        key=(id(self.cache),self.mode(),self.variant_index(),self.canvas.anchor if self.mode()=='features' else None)
        if self.layer_key!=key:
            arr=scope.draw_layer(self.photo,self.cache,self.mode(),self.variant_index(),self.canvas.anchor)
            self.canvas.layer=rgb_image(arr);self.layer_key=key;self.canvas.update()
        self.scope_state.setText('左 · 观察    /    右 · 成片')
        self.canvas.setToolTip('拖动中线，对照观察层和成片。' if self.mode()!='features' else '点照片任意位置取样；拖动中线查看对照。')
    def toggle(self):
        enabled=self.photo is not None and not self.exporting
        for widget in (self.controls,self.reset,self.compare,self.strip,self.resolution):widget.setEnabled(enabled)
        for look in self.looks.values():look.setEnabled(not self.exporting)
        self.save.setEnabled(self.photo is not None);self.open_btn.setEnabled(not self.exporting);self.folder.setEnabled(not self.exporting)
    def notice(self,msg):self.message.setText(msg);self.message.setToolTip(msg)
    def pick(self):
        if self.exporting:return
        filters=' '.join('*.'+ext for ext in sorted(eng.RAW|eng.RASTER));path,_=QFileDialog.getOpenFileName(self,'打开照片','',f'照片 ({filters});;所有文件 (*)')
        if path:self.open_photo(path)
    def dragEnterEvent(self,event):
        if not self.exporting and event.mimeData().hasUrls() and any(url.isLocalFile() for url in event.mimeData().urls()):event.acceptProposedAction()
    def dropEvent(self,event):
        if not self.exporting:
            urls=[url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()];
            if urls:self.open_photo(urls[0])
    def reset_tone(self):
        self.controls.reset()
    def open_photo(self,path):
        if self.exporting:return
        self.load_abort.set();self.load_abort=threading.Event();cancelled=self.load_abort.is_set
        self.invalidate_preview();self.stop_masks();self.look_frames.clear();self.scan=None;self.output=None
        self.canvas.split=.5;self.canvas.anchor=(.5,.5);self.canvas.hover_cell=None;self.canvas.dragging=False;self.canvas.layer=QImage();self.layer_key=None;self.scope_state.setText('等待当前预览')
        self.timer.stop();self.adjusting=False;self.controls.deferred=False;self.photo=None;self.cache=None;self.compare.setChecked(False);self.canvas.compare_image=QImage();self.canvas.compare_split=.5;self.reset_tone();self.reveal.hide();self.canvas.picture=QImage();self.canvas.update();self.toggle();self.file_label.setText(Path(path).name);self.file_label.setToolTip(str(path));self.notice('正在读取照片…');self.enqueue('load',lambda progress:eng.load(path,cancelled))
    def enqueue(self,kind,fn):self.version+=1;self.intent=(kind,self.version,fn);self.dispatch()
    def dispatch(self):
        if self.active or not self.intent or self.closing:return
        kind,version,fn=self.intent;self.intent=None;job=Job(fn);self.active=(kind,version,job)
        job.signal.done.connect(self.finished);job.signal.failed.connect(self.failed);job.signal.progress.connect(self.progress_update);self.pool.start(job)
    @Slot(int,int)
    def progress_update(self,done,total):
        self.progress.setRange(0,total);self.progress.setValue(done);self.notice('正在处理原图  ·  '+str(round(done/total*100))+'%')
    @Slot(object)
    def finished(self,result):
        kind,version,_=self.active;self.active=None
        if self.closing:return
        if version==self.version:
            if kind=='load':
                self.photo=result;self.file_label.setToolTip(str(result.path)+'\n'+result.method);self.input_view=eng.display(result.proxy[result.crop]);self.canvas.show_array(self.input_view);self.toggle();self.notice('正在显影…');self.request_preview()
            elif kind=='scan' and self.pending==self.preview_key():
                self.scan=result;self.begin_render()
            elif kind=='render' and self.pending==self.preview_key():
                self.cache,edge,view,original=result;self.output=(self.cache[0],edge,view,original);self.pending=None;self.stop_masks();self.paint_live();self.notice('预览就绪')
            elif kind=='export':
                self.end_export();self.last=result;self.reveal.show();self.notice('已保存 TIFF + JPEG  ·  '+result.stem)
        self.dispatch()
    @Slot(str)
    def failed(self,error):
        kind,version,_=self.active;self.active=None
        if self.closing:return
        if version==self.version:
            if kind=='export':self.end_export()
            elif kind in ('scan','render'):self.pending=None;self.stop_masks();self.paint_live()
            if error=='已取消':self.notice('已取消，未保存成片。')
            else:
                self.notice('未完成  ·  '+error);QMessageBox.warning(self,NAME,error)
        self.dispatch()
    def holding(self):return self.controls.plot.drag or any(item.isSliderDown() for item in self.controls.sliders.values())
    def pause_edits(self):
        if not self.photo or self.exporting:return
        self.timer.stop()
        if not self.adjusting:
            self.adjusting=True;self.controls.deferred=True;self.invalidate_preview();self.stop_masks();self.notice('调整中…')
            if not self.comparing:self.scope_state.setText('上一帧' if self.scan else '')
    def edited(self,*args):
        if not self.photo or self.exporting:return
        self.pause_edits()
        if not self.holding():self.timer.start(500)
    def release(self):
        if self.photo and not self.exporting:self.timer.start(500)
    def paint_live(self):
        if not self.photo:return
        settings=self.params()
        if self.output and self.output[0]==settings:view,source=self.output[2:]
        elif self.scan and self.scan[0]==settings:view,source=self.scan[1],self.input_view
        elif self.output:view,source=self.output[2:]
        else:view,source=self.input_view,None
        self.canvas.show_array(view,source);self.refresh_layer()
    def request_preview(self,*args):
        if not self.photo or self.exporting or self.holding():return
        self.adjusting=False;self.controls.deferred=False;self.controls.plot.update()
        self.timer.stop();key=self.preview_key()
        if self.pending==key:return
        self.invalidate_preview()
        if self.ready():self.stop_masks();self.paint_live();self.notice('预览就绪');return
        self.pending=key;self.preview_abort=threading.Event();photo=self.photo;model=self.engine;settings,edge=key
        self.notice(f'正在显影  ·  {edge} px')
        if self.scan and self.scan[0]==settings:self.begin_render();return
        self.options=eng.ort.RunOptions();options=self.options;self.paint_live();self.enqueue('scan',lambda progress:model.analyze_preview(photo,settings,options))
    def begin_render(self):
        photo=self.photo;model=self.engine;scan=self.scan;edge=self.pending[1];cancel=self.preview_abort.is_set
        self.options=eng.ort.RunOptions();options=self.options;self.enqueue('render',lambda progress:model.render_preview(photo,scan,edge,cancel,options));self.paint_live()
    def set_comparison(self,value):
        self.comparing=value;self.compare.setText('返回显影透视' if value else '原图对比');self.canvas.dragging=False;self.canvas.hover_cell=None
        self.layers.setEnabled(not value);self.variants.setEnabled(not value)
        if value:self.stop_masks();self.canvas.setToolTip('拖动中线，左侧原图，右侧成片。')
        elif self.adjusting:self.scope_state.setText('上一帧' if self.scan else '')
        self.paint_live()
    def choose_dir(self):
        directory=QFileDialog.getExistingDirectory(self,'选择输出文件夹',str(self.directory or (self.photo.path.parent if self.photo else Path.home())))
        if directory:self.directory=Path(directory);self.folder.setText('保存到：'+(self.directory.name or directory)+'  ›');self.folder.setToolTip(directory)
    def open_folder(self):
        if self.last:QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last.parent)))
    def start_export(self):
        if self.exporting:self.abort.set();self.notice('正在取消…');return
        if not self.photo:return
        self.timer.stop();self.adjusting=False;self.controls.deferred=False;self.invalidate_preview();self.stop_masks();self.paint_live()
        photo=self.photo;settings=self.params();cache=self.scan;model=self.engine;directory=self.directory or photo.path.parent
        self.abort.clear();self.exporting=True;self.toggle();self.save.setText('取消处理');self.reveal.hide();self.notice('正在读取原尺寸照片…');self.progress.setRange(0,0);self.progress.show()
        def run(progress):
            controls=cache[2] if cache and cache[0]==settings else model.predict(photo,settings)[1]
            return eng.export(model,photo,settings,controls,directory,progress,self.abort.is_set)
        self.enqueue('export',run)
    def end_export(self):
        self.exporting=False;self.progress.hide();self.save.setText('处理全图');self.toggle()
        if not self.ready():self.timer.start(0)
    def closeEvent(self,event):
        self.load_abort.set()
        if self.exporting and QMessageBox.question(self,NAME,'取消当前处理并退出？')!=QMessageBox.Yes:event.ignore();return
        self.closing=True
        if hasattr(self,'notices'):self.notices.stop()
        self.timer.stop();self.stop_masks();self.invalidate_preview();self.abort.set();self.pool.waitForDone();event.accept()

def appearance(app):
    app.setStyle('Fusion');app.setStyleSheet(CSS)
    font_id=QFontDatabase.addApplicationFont(str(eng.ASSETS/'Interface.ttf'))
    families=QFontDatabase.applicationFontFamilies(font_id) if font_id>=0 else []
    font=app.font();font.setFamilies(families+['Segoe UI','PingFang SC','Microsoft YaHei UI','sans-serif']);app.setFont(font)

def main():
    if len(sys.argv)==3 and sys.argv[1]=='--self-test':
        from check_app import run
        return run(sys.argv[2])
    app=QApplication(sys.argv);app.setApplicationName(NAME);appearance(app)
    window=Window();window.show();window.notices=StartupNotices(window)
    if len(sys.argv)>1 and Path(sys.argv[1]).is_file():QTimer.singleShot(0,lambda:window.open_photo(sys.argv[1]))
    QTimer.singleShot(0,window.notices.start)
    return app.exec()

if __name__=='__main__':sys.exit(main())
