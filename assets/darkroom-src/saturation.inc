if(process_saturation_vibrance)
    {
      const float average = (out[k] + out[k+1] + out[k+2]) / 3;
      const float delta = sqrtf( (average-out[k])*(average-out[k])+(average-out[k+1])*(average-out[k+1])+(average-out[k+2])*(average-out[k+2]));
      const float P = vibrance * (1 - powf(delta, fabsf(vibrance)));

      for(size_t c = 0; c < 3; c++)
      {
        out[k + c] = average + (saturation + P) * (out[k+c] - average);
      }
    }