from PySide6.QtCore import Qt,QRectF,QPointF,Signal
from PySide6.QtGui import QColor,QPainter,QPainterPath,QPen
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QSlider,QPushButton,QTabWidget,QComboBox,QDoubleSpinBox,QScrollArea
import numpy as np
import darkroom as dr
from m9_grain import ANCHORS

COLORS=('#dfded1','#ed856e','#80c4a3','#89b7ed')
NAMES=('总明度','红通道','绿通道','蓝通道')
ZONES=('深阴影','阴影','中灰','亮部','高光')

def screen(value):return np.where(value<=.0031308,12.92*value,1.055*np.maximum(value,0)**(1/2.4)-.055)
def linear(value):return np.where(value<=.04045,value/12.92,((value+.055)/1.055)**2.4)

class Plot(QWidget):
    def __init__(self,editor):
        super().__init__();self.editor=editor;self.drag=False;self.setMinimumHeight(145);self.setMaximumHeight(196);self.setAccessibleName('影调曲线');self.setToolTip('拖动节点调整输出。横轴为输入，纵轴为输出；黑白端点固定。')
    def box(self):return QRectF(self.rect()).adjusted(11,9,-11,-9)
    def paintEvent(self,event):
        paint=QPainter(self);paint.setRenderHint(QPainter.Antialiasing);area=self.box();paint.fillRect(area,QColor('#1c2021'));paint.setPen(QPen(QColor('#373e3e'),1))
        for frac in (.25,.5,.75):
            xpos=area.left()+frac*area.width();ypos=area.top()+frac*area.height();paint.drawLine(QPointF(xpos,area.top()),QPointF(xpos,area.bottom()));paint.drawLine(QPointF(area.left(),ypos),QPointF(area.right(),ypos))
        paint.setPen(QPen(QColor('#686f6f'),1,Qt.DashLine));paint.drawLine(area.bottomLeft(),area.topRight());channel=self.editor.channel.currentIndex();points=self.editor.points[channel];color=QColor(COLORS[channel]);axes=np.linspace(0,1,161);indices=(linear(axes)*65536).astype('int32').clip(0,65535)
        levels=axes if tuple(points)==dr.KNOTS else screen(np.interp(linear(axes),np.array(dr.KNOTS)/10000,np.array(points)/10000)) if self.editor.deferred else screen(dr.curve(tuple(points))[0][indices].astype('f')/65536);path=QPainterPath()
        for idx,(xx,yy) in enumerate(zip(axes,levels)):
            pos=QPointF(area.left()+xx*area.width(),area.bottom()-yy*area.height());path.moveTo(pos) if idx==0 else path.lineTo(pos)
        paint.setPen(QPen(color,2));paint.drawPath(path)
        for idx,(xx,yy) in enumerate(zip(dr.KNOTS,points)):
            pos=QPointF(area.left()+float(screen(xx/10000))*area.width(),area.bottom()-float(screen(yy/10000))*area.height());selected=idx==self.editor.zone.currentIndex()+1;paint.setBrush(color if selected else QColor('#242728'));radius=5 if selected else 3;paint.drawEllipse(pos,radius,radius)
    def mousePressEvent(self,event):
        if event.button()!=Qt.LeftButton:return
        self.drag=True;self.editor.pressed.emit();frac=(event.position().x()-self.box().left())/self.box().width();idx=int(np.argmin(np.abs(screen(np.array(dr.KNOTS[1:-1])/10000)-frac)))+1;self.editor.zone.setCurrentIndex(idx-1);self.move_point(event.position())
    def move_point(self,pos):
        frac=np.clip((self.box().bottom()-pos.y())/self.box().height(),0,1);self.editor.set_level(round(float(linear(frac))*10000))
    def mouseMoveEvent(self,event):
        if self.drag:self.move_point(event.position())
    def mouseReleaseEvent(self,event):
        if self.drag:self.drag=False;self.editor.released.emit()

class Controls(QTabWidget):
    changed=Signal();pressed=Signal();released=Signal();deferred=False
    def __init__(self):
        super().__init__();self.points=[list(dr.KNOTS) for _ in range(4)];self.sliders={};self.readouts={};self.layouts=[]
        for name in ('光线','颜色','曲线','质感'):
            page=QWidget();layout=QVBoxLayout(page);layout.setContentsMargins(4,11,4,4);layout.setSpacing(7);scroll=QScrollArea();scroll.setFrameShape(QScrollArea.NoFrame);scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);scroll.setWidgetResizable(True);scroll.setWidget(page);self.addTab(scroll,name);self.layouts.append(layout)
        cfg=[('ev','曝光',-300,300,0),('brightness','亮度',-100,100,0),('contrast','对比度',-95,200,0),('shoulder','高光压缩',0,100,0),('saturation','饱和度',-100,100,1),('vibrance','自然饱和度',-100,100,1)]
        cfg.append(('chroma','降彩噪',0,100,3))
        for key,name,low,high,tab in cfg:
            row=QHBoxLayout();row.addWidget(QLabel(name));row.addStretch();text=QLabel('');text.setObjectName('micro');row.addWidget(text);layout=self.layouts[tab];layout.addLayout(row);slider=QSlider(Qt.Horizontal);slider.setAccessibleName(name);slider.setRange(low,high);slider.setPageStep(10);slider.setMinimumHeight(20);layout.addWidget(slider);self.sliders[key]=slider;self.readouts[key]=text;slider.valueChanged.connect(self.emit_change);slider.sliderReleased.connect(self.released)
        row=QHBoxLayout();self.layouts[0].addLayout(row)
        for name,idx in [('调阴影',1),('调高光',4)]:
            btn=QPushButton(name);row.addWidget(btn);btn.clicked.connect(lambda checked=False,value=idx:self.open_curve(0,value))
        note=QLabel('单独调红、绿、蓝，请打开通道曲线。');note.setObjectName('micro');note.setWordWrap(True);self.layouts[1].addWidget(note);btn=QPushButton('打开通道曲线');btn.clicked.connect(lambda:self.open_curve(1,2));self.layouts[1].addWidget(btn)
        layout=self.layouts[2];self.channel=QComboBox();self.channel.setAccessibleName('曲线通道');self.channel.addItems(NAMES);layout.addWidget(self.channel);self.zone=QComboBox();self.zone.setAccessibleName('曲线控制点');self.zone.addItems(ZONES);self.zone.setCurrentIndex(2);self.plot=Plot(self);layout.addWidget(self.plot);row=QHBoxLayout();row.addWidget(self.zone);self.level=QDoubleSpinBox();self.level.setAccessibleName('节点输出百分比');self.level.setDecimals(2);self.level.setSingleStep(.1);self.level.setSuffix(' %');self.level.setKeyboardTracking(False);row.addWidget(self.level);layout.addLayout(row);self.info=QLabel();self.info.setObjectName('micro');layout.addWidget(self.info);btn=QPushButton('重置当前曲线');btn.clicked.connect(self.reset_curve);layout.addWidget(btn)
        self.sliders['chroma'].setValue(dr.DEFAULT.chroma);layout=self.layouts[3];layout.addWidget(QLabel('M9 颗粒'));self.grain=QComboBox();self.grain.setAccessibleName('M9 颗粒浓度')
        for slider in self.sliders.values():slider.sliderPressed.connect(self.pressed)
        for name,value in (('关闭',0),('轻柔',55),('标准',100),('浓郁',140)):self.grain.addItem(name,value)
        self.grain.setCurrentIndex(self.grain.findData(dr.DEFAULT.grain));layout.addWidget(self.grain);layout.addWidget(QLabel('颗粒 ISO'));self.iso=QComboBox();self.iso.setAccessibleName('颗粒 ISO');self.iso.addItem('跟随拍摄 ISO',0)
        for iso in ANCHORS[:,0]:self.iso.addItem('ISO '+str(int(iso)),int(iso))
        layout.addWidget(self.iso);self.grain.currentIndexChanged.connect(self.emit_change);self.iso.currentIndexChanged.connect(self.emit_change)
        for layout in self.layouts:layout.addStretch()
        self.channel.currentIndexChanged.connect(self.refresh);self.zone.currentIndexChanged.connect(self.refresh);self.level.valueChanged.connect(lambda value:self.set_level(round(value*100)));self.refresh();self.emit_change()
    def open_curve(self,channel,zone):self.channel.setCurrentIndex(channel);self.zone.setCurrentIndex(zone);self.setCurrentIndex(2)
    def refresh(self,*_):
        idx=self.zone.currentIndex()+1;points=self.points[self.channel.currentIndex()];self.level.blockSignals(True);self.level.setRange(points[idx-1]/100,points[idx+1]/100);self.level.setValue(points[idx]/100);self.level.blockSignals(False);self.info.setText(f'线性输入 {dr.KNOTS[idx]/100:.2f}%  →  输出 {points[idx]/100:.2f}%');self.plot.update()
    def set_level(self,value):
        idx=self.zone.currentIndex()+1;points=self.points[self.channel.currentIndex()];value=max(points[idx-1],min(value,points[idx+1]));
        if points[idx]!=value:points[idx]=value;self.refresh();self.changed.emit()
    def reset_curve(self):self.points[self.channel.currentIndex()]=list(dr.KNOTS);self.refresh();self.changed.emit()
    def reset(self):
        for key,slider in self.sliders.items():slider.blockSignals(True);slider.setValue(getattr(dr.DEFAULT,key));slider.blockSignals(False)
        for combo,value in ((self.grain,dr.DEFAULT.grain),(self.iso,dr.DEFAULT.grain_iso)):combo.blockSignals(True);combo.setCurrentIndex(combo.findData(value));combo.blockSignals(False)
        self.points=[list(dr.KNOTS) for _ in range(4)];self.refresh();self.emit_change()
    def emit_change(self,*_):
        for key,slider in self.sliders.items():
            value=slider.value();self.readouts[key].setText(f'{value/100:+.2f} EV' if key=='ev' else f'{value:+d}%' if value else '0%')
        self.changed.emit()
    def settings(self):return dr.Grade(**{key:slider.value() for key,slider in self.sliders.items()},curves=tuple(tuple(points) for points in self.points),grain=self.grain.currentData(),grain_iso=self.iso.currentData())
