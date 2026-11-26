#ifdef _WIN32
#define PUBLIC __declspec(dllexport)
#else
#define PUBLIC __attribute__((visibility("default")))
#endif

PUBLIC void jtl_flat_exchange(const unsigned short *original, const unsigned short *source,
                              const unsigned char *links, unsigned short *output,
                              int rows, int width, int step) {
    for (int row = 0; row < rows; ++row) {
        for (int column = 0; column < width-step; ++column) {
            int weight = links[row*(width-step)+column];
            if (!weight) continue;
            for (int channel = 0; channel < 3; ++channel) {
                int left = (row*width+column)*3+channel;
                int right = left+step*3;
                int delta = (original[right]-original[left]) - (source[right]-source[left]);
                if (delta < -(int)original[left]) delta = -(int)original[left];
                if (delta < original[right]-65535) delta = original[right]-65535;
                if (delta > 65535-original[left]) delta = 65535-original[left];
                if (delta > original[right]) delta = original[right];
                int flux = delta >= 0 ? (delta*weight+510)/1020 : -((-delta*weight+510)/1020);
                output[left] += flux;
                output[right] -= flux;
            }
        }
    }
}
