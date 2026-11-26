from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np
import tifffile
from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import darkroom
import engine
import flat_refinement as refinement
import vivid_refinement


def never():return False


def phase_energy(codes,period):
    values = codes.astype(np.float64) @ engine.LUMA / 257
    height,width = values.shape
    center = values[2*period:(height//period-2)*period,2*period:(width//period-2)*period]
    high = center - cv2.GaussianBlur(center,(0,0),period)
    phases = high.reshape(high.shape[0]//period,period,high.shape[1]//period,period).mean((0,2))
    return float(phases.std())


class FlatRefinement(unittest.TestCase):
    def test_vivid_preserves_real_contrast_and_bounds_periodic_correction(self):
        rows, cols = np.indices((256,384))
        wave = np.rint(64 * np.sin(2*np.pi*cols/16)).astype(np.int32)
        source = np.repeat((22000 + cols*8 + wave)[...,None],3,axis=2).astype(np.uint16)
        output = ((source.astype(np.int32)-22000)*4+30000).astype(np.uint16)
        old = output.copy()
        mask = np.full(rows.shape,255,np.uint8)
        vivid_refinement.refine(output,source,mask,rows.shape,never)
        np.testing.assert_array_equal(output,old)
        source[:] = 28000
        output[:] = 30000 + (wave*4)[...,None]
        source[:80] += ((cols[:80]%2)*1000).astype(np.uint16)[...,None]
        output[:80] += ((cols[:80]%2)*4000).astype(np.uint16)[...,None]
        mask[:,200:220] = 0
        old = output.copy()
        vivid_refinement.refine(output,source,mask,rows.shape,never)
        np.testing.assert_array_equal(output[:78],old[:78])
        np.testing.assert_array_equal(output[mask==0],old[mask==0])
        self.assertLessEqual(np.abs(output.astype(np.int32)-old).max(),386)
        self.assertLess(phase_energy(output[100:, :190],16),phase_energy(old[100:, :190],16)*.35)
        for top in range(0,len(rows),64):
            for left in range(0,rows.shape[1],64):
                tile = np.s_[top:top+64,left:left+64]
                np.testing.assert_array_equal(output[tile].sum((0,1)),old[tile].sum((0,1)))

    def test_native_matches_integer_reference_on_both_axes(self):
        if refinement.native_exchange() is None:
            self.skipTest('Native exchange unavailable on this platform')
        random = np.random.default_rng(119)
        source = random.integers(0,65536,(93,175,3),dtype=np.uint16)
        raw = random.integers(0,65536,source.shape,dtype=np.uint16)
        gate = random.integers(0,256,raw.shape[:2],dtype=np.uint8)
        for axis in (0,1):
            for step in (1,4,16,31):
                actual,reference = raw.copy(),raw.copy()
                args = source.swapaxes(1,axis),gate.swapaxes(1,axis),step
                refinement.exchange(actual.swapaxes(1,axis),*args)
                with patch.object(refinement,'native_exchange',return_value=None):
                    refinement.exchange(reference.swapaxes(1,axis),*args)
                np.testing.assert_array_equal(actual,reference)

    def test_edges_saturation_and_exact_regional_conservation(self):
        random = np.random.default_rng(419)
        source = np.empty((173,315,3), np.uint16)
        source[:,:157] = [12000,24000,34000]
        source[:,157:] = [58000,32000,9000]
        raw = random.integers(0,65536,source.shape,dtype=np.uint16)
        raw[:15] = 0
        raw[-15:] = 65535
        output = raw.copy()
        gate = np.full(source.shape[:2],255,np.uint8)
        gate[20:24] = 0
        refinement.refine(output,source,gate,source.shape[:2],never)
        for region in (np.s_[:,:157],np.s_[:,157:]):
            np.testing.assert_array_equal(output[region].sum((0,1)),raw[region].sum((0,1)))
        np.testing.assert_array_equal(output[gate==0],raw[gate==0])
        self.assertGreater(np.abs(output.astype('i')-raw).mean(),100)

    def test_full_resolution_ramp_and_texture(self):
        height,width = 387,1003
        rows,cols = np.mgrid[:height,:width]
        source = np.broadcast_to((17000+cols*18)[...,None],(height,width,3)).copy().astype(np.uint16)
        source[:128] += ((cols[:128]//3%2)*9000).astype(np.uint16)[...,None]
        periodic = np.rint(410*np.cos(2*np.pi*rows/32))
        raw = (source + periodic[...,None]).astype(np.uint16)
        output = raw.copy()
        gate = np.full((height,width),255,np.uint8)
        refinement.refine(output,source,gate,(194,502),never)
        np.testing.assert_array_equal(output[10:115,20:-20],raw[10:115,20:-20])
        self.assertLess(phase_energy(output[150:],32),phase_energy(raw[150:],32)*.05)
        slopes = (output.astype(float)-raw)[180:350,80:-80].mean((0,2))
        self.assertLess(abs(np.polyfit(np.arange(len(slopes)),slopes,1)[0])*len(slopes),25)

    def test_shapes_and_cancellation(self):
        for height,width in ((1,1),(1,65),(47,1)):
            image = np.full((height,width,3),4200,np.uint16)
            with refinement.guides((height,width)) as (guide,gate):
                guide[:]=image
                gate[:]=255
                refinement.refine(image,guide,gate,(384,512),never)
                np.testing.assert_equal(image,4200)
                with self.assertRaises(InterruptedError):
                    refinement.refine(image,guide,gate,(384,512),lambda:True)

    def test_real_profiles_preview_export_and_tile_invariance(self):
        source = np.full((768,1024,3),32768,np.uint16)
        grade = darkroom.Grade(chroma=0,grain=0)
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            path = directory/'flat.tif'
            tifffile.imwrite(path,source,photometric='rgb')
            photo = engine.load(path)
            for profile in ('classic','vivid'):
                model = engine.Engine(profile)
                scan = model.analyze_preview(photo,grade)
                fixed = scan[4]['proxy_codes']
                with patch.object(model.refinement,'refine'):
                    baseline = model.analyze_preview(photo,grade)[4]['proxy_codes']
                np.testing.assert_array_equal(baseline.sum((0,1)),fixed.sum((0,1)))
                self.assertLess(phase_energy(fixed,16),phase_energy(baseline,16)*(.30 if profile=='vivid' else .05))
                first = np.empty_like(source)
                second = np.empty_like(source)
                for tile,dest in ((384,first),(277,second)):
                    model.tiles(photo,grade,scan[2],source,False,dest,lambda *args:None,never,tile=tile)
                np.testing.assert_array_equal(first,second)
                _,_,view,_ = model.render_preview(photo,scan,1024,never)
                expected = np.rint(first/np.float32(257)).astype(np.uint8)
                np.testing.assert_array_equal(view,expected)
                output = engine.export(model,photo,grade,scan[2],directory,lambda *args:None,never)
                tiff = tifffile.imread(output)
                self.assertLess(phase_energy(tiff,32),phase_energy(baseline,16)*(.30 if profile=='vivid' else .08))
                with Image.open(output.with_suffix('.jpg')) as jpeg:
                    self.assertEqual(jpeg.size,(1024,768))
                    self.assertTrue(jpeg.info['icc_profile'])
                print(profile,'proxy grid',phase_energy(baseline,16),phase_energy(fixed,16),'full grid',phase_energy(tiff,32), flush=True)


if __name__ == '__main__':
    unittest.main()
