import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import scene_highlights as boundary
import sensor


class SceneHighlights(unittest.TestCase):
    def test_scene_range_hue_and_reference_white(self):
        ramp=np.linspace(0,8,8001,dtype='f')
        source=ramp[:,None,None]*np.array([1,.52,.07],'f')
        model,peak=boundary.model_input(source,True)
        np.testing.assert_array_equal(model[:800],source[:800]);self.assertLessEqual(model.max(),1.)
        self.assertTrue(np.all(np.diff(model[:,0,0])>0))
        np.testing.assert_allclose(model[:,0,1],model[:,0,0]*.52,atol=2e-7)
        style=np.full_like(model,.45);clean=boundary.finish(style,source,peak,None)
        np.testing.assert_array_equal(clean[:1001],style[:1001]);np.testing.assert_allclose(clean[2000:],model[2000:],atol=1e-7)
        sdr=source[:1001];bounded,peak=boundary.model_input(sdr,False);self.assertIs(bounded,sdr);self.assertIsNone(peak)

    def test_neutral_is_evidence_based_and_color_is_not_bleached(self):
        source=np.array([[[2.28,2.50,2.29],[2.28,2.50,2.29],[.1,.4,3.7],[3.,.05,.07],[2.8,1.7,.47],[.24,.35,.36]]],'f')
        model,peak=boundary.model_input(source,True);style=np.broadcast_to(np.array([.7,.35,.4],'f'),source.shape)
        cells=np.array([[255,0,255,255,255,255]],'uint8');clean=boundary.finish(style,source,peak,cells)
        self.assertLess(np.ptp(clean[0,0]),1e-6);self.assertGreater(clean[0,0,0],.97)
        np.testing.assert_allclose(clean[0,1:5],model[0,1:5],atol=1e-7)
        np.testing.assert_array_equal(clean[0,-1],style[0,-1]);self.assertGreater(np.ptp(clean[0,1]),.07)

    def test_raw_evidence_uses_all_four_sites_and_per_site_levels(self):
        pattern=np.array([[2,3],[1,0]]);black=np.array([130,199,350,82],'f');white=np.array([4200,7440,8800,3200],'f')
        site=np.tile(pattern,(10,13));normalized=np.zeros(site.shape,'f')+.52;normalized[5:15,7:17]=1
        plane=np.rint(black[site]+normalized*(white[site]-black[site])).astype('uint16');view=lambda image:np.rot90(image[1:19,3:25]);raw=view(plane);indices=view(site)
        frac=(raw-black[indices])/(white[indices]-black[indices]);expected=frac.reshape(raw.shape[0]//2,2,raw.shape[1]//2,2).min(axis=(1,3))>.995
        actual=sensor.clipping_cells(plane,pattern,black,white,view,lambda:False);np.testing.assert_array_equal(actual,255*expected)
        plane[0::2,1::2]=np.uint16(black[3]);self.assertIsNone(sensor.clipping_cells(plane,pattern,black,white,view,lambda:False))

    def test_exposure_can_lower_a_sensor_clipped_white(self):
        after_ev=np.full((2,2,3),.59,'f');model,peak=boundary.model_input(after_ev,True);self.assertIsNone(peak)
        style=np.broadcast_to(np.array([.99,.92,.97],'f'),model.shape);cells=np.array([[255,0],[0,255]],'uint8')
        clean=boundary.finish(style,after_ev,peak,cells);np.testing.assert_allclose(clean[cells==255],.59,atol=1e-7);np.testing.assert_array_equal(clean[cells==0],style[cells==0])

    def test_evidence_resampling_has_no_tile_boundaries(self):
        cells=np.random.default_rng(19).integers(0,256,(33,50),dtype=np.uint8)
        whole=boundary.tile_evidence(cells,101,67,0,0,101,67)
        for left,top,right,bottom in [(0,0,23,17),(23,17,87,58),(87,58,101,67)]:
            region=boundary.tile_evidence(cells,101,67,left,top,right,bottom);np.testing.assert_array_equal(whole[top:bottom,left:right],region)

    @unittest.skipUnless(os.getenv('JTL_WINDOW_DNG'),'Set JTL_WINDOW_DNG to the issue #1 fixture')
    def test_issue_one_real_raw_preview_and_export(self):
        import darkroom
        import engine
        import tifffile
        from PIL import Image
        path=Path(os.environ['JTL_WINDOW_DNG']);self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),'65cbfbab6c99548c399ee8412777d38756974bff2ccdec26c5a4342d24839348')
        photo=engine.load(path);self.assertEqual(photo.method,'BayerNet')
        def check(image,scale):
            height,width=image.shape[:2];sky=image[round(height*.15):round(height*.33),round(width*.32):round(width*.385)].astype('f')/scale
            med=np.median(sky,axis=(0,1));self.assertLess(np.ptp(med),3);self.assertGreater(np.min(med),244)
            self.assertLess(np.quantile(np.ptp(sky,axis=2),.95),16)
        for profile in ('vivid','classic'):
            model=engine.Engine(profile);scan=model.analyze_preview(photo,darkroom.DEFAULT)
            for edge in engine.PREVIEW_EDGES:
                _,_,rendered,source=model.render_preview(photo,scan,edge,lambda:False);check(source,1);check(rendered,1)
            with tempfile.TemporaryDirectory() as folder:
                output=engine.export(model,photo,darkroom.DEFAULT,scan[2],Path(folder),lambda *counts:None,lambda:False)
                data=tifffile.memmap(output,mode='r');self.assertEqual(data.shape,(6128,8176,3));check(data,257);del data
                with Image.open(output.with_suffix('.jpg')) as companion:check(np.asarray(companion),1)


if __name__=='__main__':unittest.main()
