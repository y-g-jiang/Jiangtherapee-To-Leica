import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from PIL import Image
from PySide6.QtCore import QPoint,Qt
from PySide6.QtGui import QImage,QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from app import Window,appearance


def wait(qt,condition):
    deadline=time.monotonic()+90
    while time.monotonic()<deadline:
        qt.processEvents()
        if condition():return
        time.sleep(.005)
    raise TimeoutError('Preview did not reach the expected state')


def drag(canvas,start,end):
    QTest.mousePress(canvas,Qt.LeftButton,pos=start);QTest.mouseMove(canvas,end);QTest.mouseRelease(canvas,Qt.LeftButton,pos=end)


def assert_clean(canvas):
    actual=canvas.grab().toImage().convertToFormat(QImage.Format_RGB32);expected=actual.copy();paint=QPainter(expected)
    paint.setRenderHint(QPainter.Antialiasing);paint.setRenderHint(QPainter.SmoothPixmapTransform);paint.drawImage(canvas.frame,canvas.picture);paint.end()
    inside=canvas.frame.toAlignedRect().adjusted(1,1,-1,-1)
    assert actual.copy(inside)==expected.copy(inside) and canvas.edge_tab().right()<canvas.frame.left()


def run():
    qt=QApplication([]);appearance(qt);window=Window();window.show();canvas=window.canvas
    def ready():return window.ready() and not window.pending and not window.active
    def park():
        frame=canvas.frame;start=QPoint(round(frame.left()+canvas.divider()*frame.width()),round(frame.center().y()));end=QPoint(round(frame.left()),start.y());drag(canvas,start,end)
        assert canvas.parked() and not window.motion.isActive();assert_clean(canvas)
    with tempfile.TemporaryDirectory() as folder:
        landscape=Path(folder)/'first.png';portrait=Path(folder)/'second.png';image=np.random.default_rng(7).integers(0,256,(800,1600,3),dtype='uint8');Image.fromarray(image).save(landscape);Image.fromarray(image.transpose(1,0,2)).save(portrait)
        try:
            window.open_photo(landscape);wait(qt,ready);canvas.grab();assert canvas.divider()==.5
            window.layers.setCurrentIndex(window.layers.findData('features'));window.variants.setCurrentIndex(2);park()
            anchor=canvas.anchor;QTest.mouseClick(canvas,Qt.LeftButton,pos=canvas.frame.topLeft().toPoint()+QPoint(30,30));assert canvas.anchor==anchor
            window.compare.click();assert canvas.divider()==.5 and not canvas.parked();window.compare.click();assert canvas.parked();assert_clean(canvas)
            window.resolution.setCurrentIndex(window.resolution.findData(1600));assert window.motion.isActive() and canvas.parked()
            for alpha in (0.,.43,1.):
                canvas.mask_alpha=alpha;shown=canvas.grab().toImage().convertToFormat(QImage.Format_RGB32);reference=shown.copy();paint=QPainter(reference);paint.setRenderHint(QPainter.Antialiasing);paint.setRenderHint(QPainter.SmoothPixmapTransform);paint.drawImage(canvas.frame,canvas.mask_pair[0]);paint.setOpacity(alpha);paint.drawImage(canvas.frame,canvas.mask_pair[1]);paint.end();inside=canvas.frame.toAlignedRect().adjusted(1,1,-1,-1);assert shown.copy(inside)==reference.copy(inside)
            wait(qt,ready);assert canvas.parked();assert_clean(canvas)
            window.controls.sliders['brightness'].setValue(8);wait(qt,ready);assert canvas.parked();assert_clean(canvas)
            drag(canvas,canvas.edge_tab().center().toPoint(),canvas.frame.center().toPoint());assert abs(canvas.divider()-.5)<.01 and not canvas.layer.isNull() and window.variant_index()==2
            window.layers.setCurrentIndex(window.layers.findData('routing'));park();window.open_photo(portrait);assert canvas.divider()==.5;wait(qt,ready);canvas.grab();assert canvas.frame.height()>canvas.frame.width() and not canvas.layer.isNull();park()
        finally:window.close()
    print('PASS: zero image coverage, outside handle, features and routing, independent comparison, waiting animation, edit retention, new photos centered')


if __name__=='__main__':run()
