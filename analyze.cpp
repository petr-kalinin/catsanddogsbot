#include <opencv2/core/core.hpp>
#include <opencv2/highgui/highgui.hpp>

#include <string>
#include <iostream>
#include <vector>

using Color = cv::Vec4b;
using Image = cv::Mat_<Color>;
using Data = cv::Mat_<uchar>;
const Color TRANSPARENT(0,0,0,0);

enum {
    TYPE_NONE,
    TYPE_RAIN,
    TYPE_STORM,
    TYPE_HAIL,
    TYPE_UNKNOWN
};

namespace color_detector {
    bool is_rain_color(Color color) {
        int r = color[2];
        int g = color[1];
        int b = color[0];
        return b > 2*g && b > 2*r;
    }


    bool is_storm_color(Color color) {
        int r = color[2];
        int g = color[1];
        int b = color[0];
        return (r > 1.3*g && r > 2*b);
    }

    bool is_hail_color(Color color) {
        int r = color[2];
        int g = color[1];
        int b = color[0];
        return ((g > 2*r && g > 2*b) // greens
            || (r > 3*g && b > 3*g && r > 0.5*b && b > 0.5*r)); // violets
    }
        
    bool is_none_color(Color color) {
        return !(is_rain_color(color) || is_storm_color(color) || is_hail_color(color));
    }
    
    int detect(Color color) {
        if (is_rain_color(color))
            return TYPE_RAIN;
        else if (is_storm_color(color))
            return TYPE_STORM;
        else if (is_hail_color(color))
            return TYPE_HAIL;
        else if (is_none_color(color))
            return TYPE_NONE;
        else
            return TYPE_UNKNOWN;
    }
}

void colorize(const Data& data) {
    static const std::vector<Color> COLORS{
        {0, 0, 0, 255},
        {255, 0, 0, 255},
        {0, 0, 255, 255},
        {0, 255, 0, 255},
        {255, 255, 255, 255}
    };
    Image im(data.rows, data.cols, TRANSPARENT);
    for (int y = 0; y < data.rows; y++)
        for (int x = 0; x < data.cols; x++) {
            im(y, x) = COLORS[data(y,x)];
        }
    
    std::vector<int> compression_params;
    compression_params.push_back(CV_IMWRITE_PNG_COMPRESSION);
    compression_params.push_back(9);
    cv::imwrite("test.png", im, compression_params);    
}

bool isFixedColor(const std::vector<Image>& frames, int x, int y) {
    auto col = frames[0](y, x);
    if (color_detector::is_none_color(col))
        return false;
    for (const auto& frame: frames) {
        if (frame(y, x) != col)
            return false;
    }
    return true;
}

std::vector<int> makeDd() {
    std::vector<int> dd;
    for (int x = 0; x <= 5; x++)
        for (int s: {-1, 1}) 
            dd.push_back(x * s);
    return dd;
}

bool goodPoint(const Image& im, int x, int y) {
    return (x>=0) && (x<im.cols) && (y>=0) && (y<im.rows);
}

int main(int argc, char* argv[]) {
    std::string fname = argv[1];
    std::vector<Image> frames;
    for (int frame = 0; frame <= 18; frame++) {
        char buffer[100];
        sprintf(buffer, fname.c_str(), frame);
        frames.push_back(cv::imread(buffer, -1));
    }
    
    Data fixeds = Data::zeros(frames[0].rows, frames[0].cols);
    for (int y = 0; y < fixeds.rows; y++) {
        for (int x = 0; x < fixeds.cols; x++) {
            fixeds(y, x) = isFixedColor(frames, x, y);
        }
    }
        
    auto dd = makeDd();
    
    std::vector<Data> dataFrames(frames.size());
    for (const auto& frame: frames) {
        dataFrames.emplace_back(Data::zeros(frame.rows, frame.cols));
        for (int y = 0; y < frame.rows; y++) {
            for (int x = 0; x < frame.cols; x++) {
                bool found = false;
                for (int dx: dd) {
                    for (int dy: dd) {
                        int xx = x + dx;
                        int yy = y + dy;
                        if (goodPoint(frame, xx, yy) && !fixeds(yy, xx)) {
                            dataFrames.back()(y, x) = color_detector::detect(frame(yy, xx));
                            found = true;
                            break;
                        }
                    }
                    if (found) break;
                }
                if (!found)
                    dataFrames.back()(y, x) = TYPE_NONE;
            }
        }
    }
    
    colorize(dataFrames.back());
    return 0;
}
