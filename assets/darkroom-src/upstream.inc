/*
    This file is part of darktable,
    Copyright (C) 2019-2024 darktable developers.

    darktable is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    darktable is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with darktable.  If not, see <http://www.gnu.org/licenses/>.
*/

/*
   This file is part of darktable,
   Copyright (C) 2011-2022 darktable developers.

   darktable is free software: you can redistribute it and/or modify
   it under the terms of the GNU General Public License as published by
   the Free Software Foundation, either version 3 of the License, or
   (at your option) any later version.

   darktable is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   GNU General Public License for more details.

   You should have received a copy of the GNU General Public License
   along with darktable.  If not, see <http://www.gnu.org/licenses/>.

   Part of this file is based on nikon_curve.c from UFraw
   Copyright 2004-2008 by Shawn Freeman, Udi Fuchs
*/

/*
    This file is part of darktable,
    Copyright (C) 2016-2024 darktable developers.

    darktable is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    darktable is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with darktable.  If not, see <http://www.gnu.org/licenses/>.
*/

typedef struct
{
  float x;
  float y;
} CurveAnchorPoint;

typedef struct
{
  // Type for this curve
  uint32_t m_spline_type;

  // Box data
  float m_min_x;
  float m_max_x;
  float m_min_y;
  float m_max_y;

  // Number of anchor points
  uint8_t m_numAnchors;

  // contains a list of anchors, 2 floats per each point, x-y format
  // max is 20 points
  CurveAnchorPoint m_anchors[MAX_ANCHORS];

} CurveData;

typedef struct
{
  // Number of samples to use for the curve.
  uint32_t m_samplingRes;
  uint32_t m_outputRes;

  // Sampling array
  uint16_t *m_Samples; // jo: changed to short int to save memory

} CurveSample;

static inline float get_gamma(const float x, const float gamma)
{
  return powf(x, gamma);
}

static inline float get_lut_gamma(const float x, const float gamma, const float *const lut)
{
  return (x > 1.f) ? get_gamma(x, gamma) : lut[CLAMP((int)(x * 0x10000ul), 0, 0xffff)];
}

static inline float hlcurve(const float level, const float hlcomp, const float hlrange)
{
  if(hlcomp > 0.0f)
  {
    float val = level + (hlrange - 1.f);

    // to avoid division by zero
    if(val == 0.0f)
    {
      val = 0.000001f;
    }

    float Y = val / hlrange;
    Y *= hlcomp;

    // to avoid log(<=0)
    if(Y <= -1.0f)
    {
      Y = -.999999f;
    }

    float R = hlrange / (val * hlcomp);
    return log1pf(Y) * R;
  }
  else
  {
    return 1.f;
  }
}

static inline void dt_iop_estimate_exp(const float *const x, const float *const y, const int num, float *coeff)
{
  // map every thing to y = y0*(x/x0)^g
  // and fix (x0,y0) as the last point.
  // assume (x,y) pairs are ordered by ascending x, so this is the last point:
  const float x0 = x[num - 1], y0 = y[num - 1];

  float g = 0.0f;
  int cnt = 0;
  // solving for g yields
  // g = log(y/y0)/log(x/x0)
  //
  // average that over the course of the other samples:
  for(int k = 0; k < num - 1; k++)
  {
    const float yy = y[k] / y0, xx = x[k] / x0;
    if(yy > 0.0f && xx > 0.0f)
    {
      const float gg = logf(y[k] / y0) / logf(x[k] / x0);
      g += gg;
      cnt++;
    }
  }
  if(cnt)
    g *= 1.0f / cnt;
  else
    g = 1.0f;
  coeff[0] = 1.0f / x0;
  coeff[1] = y0;
  coeff[2] = g;
}

static inline float dt_iop_eval_exp(const float *const coeff, const float x)
{
  return coeff[1] * powf(x * coeff[0], coeff[2]);
}

float *monotone_hermite_set(int n, float x[], float y[])
{
  if(n <= 1)
  {
    // nc_message(NC_SET_ERROR, "spline_cubic_set() error: "
    //   "The number of data points must be at least 2.\n");
    return NULL;
  }

  for(int i = 0; i < n - 1; i++)
  {
    if(x[i + 1] <= x[i])
    {
      // nc_message(NC_SET_ERROR, "spline_cubic_set() error: "
      //   "The knots must be strictly increasing, but "
      //  "T(%u) = %e, T(%u) = %e\n",i,x[i],i+1,x[i+1]);
      return NULL;
    }
  }

  float *delta = calloc(n, sizeof(float));
  // nc_merror(delta, "spline_cubic_set");
  float *m = calloc(n + 1, sizeof(float));
  // nc_merror(m, "spline_cubic_set");
  // calculate the slopes
  for(int i = 0; i < n - 1; i++)
  {
    delta[i] = (y[i + 1] - y[i]) / (x[i + 1] - x[i]);
  }
  delta[n - 1] = delta[n - 2];

  m[0] = delta[0];
  m[n - 1] = delta[n - 1];

  for(int i = 1; i < n - 1; i++)
  {
    m[i] = (delta[i - 1] + delta[i]) * .5f;
  }
  for(int i = 0; i < n; i++)
  {
    if(fabsf(delta[i]) < EPSILON)
    {
      m[i] = 0.0f;
      m[i + 1] = 0.0f;
    }
    else
    {
      const float alpha = m[i] / delta[i];
      const float beta = m[i + 1] / delta[i];
      const float tau = alpha * alpha + beta * beta;
      if(tau > 9.0f)
      {
        m[i] = 3.0f * alpha * delta[i] / sqrtf(tau);
        m[i + 1] = 3.0f * beta * delta[i] / sqrtf(tau);
      }
    }
  }
  free(delta);
  return m;
}

float catmull_rom_val(int n, float x[], float xval, float y[], float tangents[])
{
  //
  //  Determine the interval [ T(I), T(I+1) ] that contains TVAL.
  //  Values below T[0] or above T[N-1] use extrapolation.
  //
  int ival = n - 2;

  for(int i = 0; i < n - 2; i++)
  {
    if(xval < x[i + 1])
    {
      ival = i;
      break;
    }
  }

  const float m0 = tangents[ival];
  const float m1 = tangents[ival + 1];
  //
  //  In the interval I, the polynomial is in terms of a normalized
  //  coordinate between 0 and 1.
  //
  const float h = x[ival + 1] - x[ival];
  const float dx = (xval - x[ival]) / h;
  const float dx2 = dx * dx;
  const float dx3 = dx * dx2;

  const float h00 = (2.0 * dx3) - (3.0 * dx2) + 1.0;
  const float h10 = (1.0 * dx3) - (2.0 * dx2) + dx;
  const float h01 = (-2.0 * dx3) + (3.0 * dx2);
  const float h11 = (1.0 * dx3) - (1.0 * dx2);

  return (h00 * y[ival]) + (h10 * h * m0) + (h01 * y[ival + 1]) + (h11 * h * m1);
}

int CurveDataSample(CurveData *curve, CurveSample *sample)
{
  int n = 0;

  float x[20] = { 0 };
  float y[20] = { 0 };

  // The box points are what the anchor points are relative
  // to so...

  const float box_width = curve->m_max_x - curve->m_min_x;
  const float box_height = curve->m_max_y - curve->m_min_y;

  // build arrays for processing
  if(curve->m_numAnchors == 0)
  {
    // just a straight line using box coordinates
    x[0] = curve->m_min_x;
    y[0] = curve->m_min_y;
    x[1] = curve->m_max_x;
    y[1] = curve->m_max_y;
    n = 2;
  }
  else
  {
    for(int i = 0; i < curve->m_numAnchors; i++)
    {
      x[i] = curve->m_anchors[i].x * box_width + curve->m_min_x;
      y[i] = curve->m_anchors[i].y * box_height + curve->m_min_y;
    }
    n = curve->m_numAnchors;
  }
  const float res = 1.0 / (float)(sample->m_samplingRes - 1);
  const int firstPointX = x[0] * (sample->m_samplingRes - 1);
  const int firstPointY = y[0] * (sample->m_outputRes - 1);
  const int lastPointX = x[n - 1] * (sample->m_samplingRes - 1);
  const int lastPointY = y[n - 1] * (sample->m_outputRes - 1);
  const int maxY = curve->m_max_y * (sample->m_outputRes - 1);
  const int minY = curve->m_min_y * (sample->m_outputRes - 1);
  // returns an array of second derivatives used to calculate the spline curve.
  // this is a malloc'd array that needs to be freed when done.
  // The settings currently calculate the natural spline, which closely matches
  // camera curve output in raw files.
  float *ypp = interpolate_set(n, x, y, curve->m_spline_type);
  if(ypp == NULL) return CT_ERROR;

  for(int i = 0; i < (int)sample->m_samplingRes; i++)
  {
    // get the value of the curve at a point
    // take into account that curves may not necessarily begin at x = 0.0
    // nor end at x = 1.0

    // Before the first point and after the last point, take a strait line
    if(i < firstPointX)
    {
      sample->m_Samples[i] = firstPointY;
    }
    else if(i > lastPointX)
    {
      sample->m_Samples[i] = lastPointY;
    }
    else
    {
      // within range, we can sample the curve
      int val = interpolate_val(n, x, i * res, y, ypp, curve->m_spline_type) * (sample->m_outputRes - 1) + 0.5;
      if(val > maxY) val = maxY;
      if(val < minY) val = minY;
      sample->m_Samples[i] = val;
    }
  }

  free(ypp);
  return CT_SUCCESS;
}