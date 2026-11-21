import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import engine
import highlights
import sensor


def never():return False


class Highlights(unittest.TestCase):
    def test_pinned_color_propagation(self):
        rows,cols=np.mgrid[:224,:288].astype('f');wb=np.array([2.25,1,1.875],'f')
        power=.075+4*np.maximum(0,1-((cols-139)/90)**2-((rows-113)/78)**2)
        camera=np.minimum(power[...,None]*np.array([1.02,.95,.72],'f'),wb)
        actual=highlights.recover(camera.copy(),wb,wb*65535,never)
        np.testing.assert_allclose(actual[113,139],[2.3078513,2.1494691,1.6290716],atol=4e-5)
        np.testing.assert_allclose(actual[65,110],[2.1877961,2.0376525,1.5443268],atol=4e-5)
        np.testing.assert_array_equal(actual[0,0],camera[0,0]);self.assertGreater(np.ptp(actual[113,139]),.6)
        if sys.platform=='win32':self.assertEqual(hashlib.sha256(actual).hexdigest(),'ce8deb1867294b057b877a22ae8f3e5f18fb6cbb948342073701eddad68f0e29')

    def test_original_raw_site_maxima(self):
        sites=np.array([[16000,13000],[14500,14900]],'uint16');plane=np.tile(sites,(32,48));pattern=np.array([[0,1],[3,2]]);colors=np.array([[0,1],[1,2]])
        wb=np.array([2.2,1,1.9,1.05],'f');black=np.array([512,512,512,528],'f');white=np.full(4,15360,'f')
        signal,observed=sensor.camera_mosaic(plane,pattern,colors,black,white,wb,max(wb),never)
        expected=[(16000-512)/14848*wb[0],max((13000-512)/14848,(14500-528)/(15360-528)),(14900-512)/14848*wb[2]]
        np.testing.assert_allclose(observed,np.array(expected)*65535,rtol=2e-7);self.assertEqual(signal[0,0],1.)

    def test_global_camera_domain_and_preview_order(self):
        height,width=96,136;plane=np.full((height,width),4000,'uint16');matrix=np.array([[1.5,-.5,0],[0,1.3,-.3],[.1,-.4,1.3]],'f')
        pat=np.array([[0,1],[3,2]]);raw=SimpleNamespace(sizes=SimpleNamespace(height=height,width=width,iheight=height,iwidth=width,top_margin=0,left_margin=0,pixel_aspect=1.,flip=5),raw_pattern=pat,color_desc=b'RGBG',raw_image_visible=plane,raw_color=lambda row,col:pat[row,col],black_level_per_channel=[512]*4,camera_white_level_per_channel=[15360]*4,white_level=16383,camera_whitebalance=[2.,1.,1.8,1.],color_matrix=matrix,visible_crop=(5,8,120,80))
        camera=np.random.default_rng(30).random((height,width,3),dtype=np.float32);oriented=np.rot90(camera[8:88,5:125]);wb=np.array(raw.camera_whitebalance,'f');seen=[]
        def spy(rgb,actual_wb,observed,cancelled):
            np.testing.assert_array_equal(rgb,oriented);self.assertTrue(rgb.flags.c_contiguous);np.testing.assert_array_equal(wb,actual_wb);seen.append(rgb.shape);return rgb
        with patch.object(sensor,'demosaic',return_value=camera),patch.object(highlights,'recover',side_effect=spy):
            actual=sensor.read(raw,True,never,quick_edge=60)
        expected=np.maximum(cv2.resize(oriented,(40,60),interpolation=cv2.INTER_AREA)@matrix.T,0)
        np.testing.assert_allclose(actual,expected,atol=1e-6);self.assertEqual(seen,[(120,80,3)])

    def test_rgb_bypass_and_cancel(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(highlights,'recover',side_effect=AssertionError('unexpected RAW recovery')):
            photo=Path(folder)/'photo.jpg';Image.new('RGB',(80,40)).save(photo);self.assertEqual(engine.load(photo).method,'RGB')
        with self.assertRaises(InterruptedError):highlights.recover(np.ones((32,32,3),'f'),np.ones(3,'f'),np.ones(3,'f'),lambda:True)


if __name__=='__main__':unittest.main()
