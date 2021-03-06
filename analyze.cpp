#include <opencv2/core/core.hpp>
#include <opencv2/highgui/highgui.hpp>
#include <opencv2/imgproc/imgproc.hpp>
#include <opencv2/video/tracking.hpp>

#include <string>
#include <iostream>
#include <fstream>
#include <vector>
#include <queue>
#include <cmath>
#include <set>
#include <map>

#include <boost/optional/optional.hpp>

using Color = cv::Vec4i;
using Image = cv::Mat_<Color>;
using Data = cv::Mat_<uchar>;
using RichData = cv::Mat_<float>;
using Flow = cv::Mat_<cv::Vec2f>;

const Color TRANSPARENT(0,0,0,0);

const int TYPE_NO_DATA = 0;
const int TYPE_NONE = 1;
const int TYPE_CLOUD = 2;
const int TYPE_RAIN = 3;
const int TYPE_STORM = 4;
const int TYPE_HAIL = 5;
const int TYPE_UNKNOWN = 6;

const double MERGE_THRESHOLD = 7;

const double PERIOD = 10;

std::map<std::string, std::pair<int, int>> POINTS {
    {"nnov:center", {448, 612}},
    {"nnov:avtozavod", {450, 607}},
    {"nnov:sormovo", {445, 608}},
    {"msk:center", {452, 462}},
    {"msk:north", {446, 462}},
    {"msk:south", {458, 462}},
    {"msk:west", {452, 457}},
    {"msk:east", {452, 466}},
    {"spb:center", {244, 344}},
    {"spb:north", {236, 344}},
    {"spb:south", {249, 344}},
    {"spb:east", {244, 347}},
    {"sis:", {374, 568}}
    
};

namespace color_detector {
    
    bool is_cloud_color(const Color& color) {
        int r = color[2];
        int g = color[1];
        int b = color[0];
        return (b > 0.8*g && g > 0.4*b && b > 3*r)
            || (b > 3*g && b > 3*r && b >= 170);  // light blue
    }
    
    bool is_rain_color(const Color& color) {
        int r = color[2];
        int g = color[1];
        int b = color[0];
        return b > 3*g && b > 3*r && b < 170;
    }


    bool is_storm_color(const Color& color) {
        int r = color[2];
        int g = color[1];
        int b = color[0];
        return (r > 1.3*g && r > 3*b);
    }

    bool is_hail_color(const Color& color) {
        int r = color[2];
        int g = color[1];
        int b = color[0];
        return ((g > 2*r && g > 3*b) // greens
            || (r > 3*g && b > 3*g && r > 0.5*b && b > 0.5*r)); // violets
    }
        
    bool is_none_color(const Color& color) {
        int r = color[2];
        int g = color[1];
        int b = color[0];
        int a = (r + g + b)/3;
        return (r > 0.8*a && g > 0.8*a && b > 0.8*a && a < 160 && a > 60)  // grays
            || (r > 3*b && g > 3*b && r > 0.8*g && g > 0.8*r);  // yellows
    }
    
    bool is_no_data_color(const Color& color) {
        int r = color[2];
        int g = color[1];
        int b = color[0];
        int a = (r + g + b)/3;
        return (r > 0.8*a && g > 0.8*a && b > 0.8*a && a >= 160);
    }
    
    int detect(const Color& color) {
        if (is_hail_color(color))
            return TYPE_HAIL;
        else if (is_storm_color(color))
            return TYPE_STORM;
        else if (is_rain_color(color))
            return TYPE_RAIN;
        else if (is_cloud_color(color))
            return TYPE_CLOUD;
        else if (is_none_color(color))
            return TYPE_NONE;
        else if (is_no_data_color(color))
            return TYPE_NO_DATA;
        else
            return TYPE_UNKNOWN;
    }
}

void colorize(const Data& data, const std::string& filename) {
    static const std::vector<Color> COLORS{
        {0, 0, 0, 255},
        {128, 128, 128, 255},
        {128, 0, 0, 255},
        {255, 0, 0, 255},
        {0, 0, 255, 255},
        {0, 255, 0, 255},
        {255, 0, 255, 255}
    };
    Image im(data.rows, data.cols, TRANSPARENT);
    for (int y = 0; y < data.rows; y++)
        for (int x = 0; x < data.cols; x++) {
            im(y, x) = COLORS[data(y,x)];
        }
    
    std::vector<int> compression_params;
    compression_params.push_back(CV_IMWRITE_PNG_COMPRESSION);
    compression_params.push_back(9);
    cv::imwrite(filename + ".png", im, compression_params);    
}

void colorize(const RichData& data, const std::string& filename) {
    Image im(data.rows, data.cols, TRANSPARENT);
    double max, min;
    cv::minMaxLoc(data, &min, &max);
    for (int y = 0; y < data.rows; y++)
        for (int x = 0; x < data.cols; x++) {
            im(y, x) = {(data(y, x) - min)/(max-min)*256, 0, 0, 255};
        }
    
    std::vector<int> compression_params;
    compression_params.push_back(CV_IMWRITE_PNG_COMPRESSION);
    compression_params.push_back(9);
    cv::imwrite(filename + ".png", im, compression_params);    
}

void colorize(const Flow& flow, const std::string& filename) {
    cv::Mat3f im(flow.rows, flow.cols, cv::Vec3f(0, 0, 0));
    for (int y = 0; y < flow.rows; y++)
        for (int x = 0; x < flow.cols; x++) {
            float vx = flow(y, x)[0];
            float vy = flow(y, x)[1];
            float v = sqrt(vx*vx + vy*vy);
            float dir = atan2(vy, vx);
            if (dir < 0) dir += 2*M_PI;
            float h = dir / 2 / M_PI * 360;
            float val = (log10(v + 1e-25) + 25) / 10;
            //if (val > 0.5) std::cout << vx << " " << vy << " " << v << std::endl;
            im(y, x) = {h, 1, val};
        }
    
    cv::Mat4f converted;
    cv::cvtColor(im, converted, cv::COLOR_HSV2BGR, 4);
    Image result = converted * 256;

    std::vector<int> compression_params;
    compression_params.push_back(CV_IMWRITE_PNG_COMPRESSION);
    compression_params.push_back(9);
    cv::imwrite(filename + ".png", result, compression_params);    
}

template<class T>
void colorize(const std::vector<T>& data, const std::string& filename) {
    for (int i = 0; i < data.size(); i++) {
        char buffer[100];
        sprintf(buffer, filename.c_str(), i);
        colorize(data[i], buffer);
    }
}

bool isFixedColor(const std::vector<Image>& frames, int x, int y) {
    auto col = frames[0](y, x);
    for (const auto& frame: frames) {
        if (frame(y, x) != col)
            return false;
    }
    return true;
}

std::vector<int> makeDd(int max) {
    std::vector<int> dd;
    for (int x = 0; x <= max; x++)
        for (int s: {-1, 1}) 
            dd.push_back(x * s);
    return dd;
}

template<class M>
bool goodPoint(const M& im, int x, int y) {
    return (x>=0) && (x<im.cols) && (y>=0) && (y<im.rows);
}

std::vector<Image> loadImages(const std::string& filename) {
    std::string fname = filename;
    std::vector<Image> frames;
    for (int frame = 9; frame <= 17; frame++) {
        char buffer[100];
        sprintf(buffer, fname.c_str(), frame);
        frames.push_back(cv::imread(buffer, -1));
    }
    return frames;
}

std::vector<Data> convertToDatas(const std::vector<Image>& frames) {
    Data fixeds = Data::zeros(frames[0].rows, frames[0].cols);
    for (int y = 0; y < fixeds.rows; y++) {
        for (int x = 0; x < fixeds.cols; x++) {
            fixeds(y, x) = isFixedColor(frames, x, y);
        }
    }
    
    auto dd = makeDd(4);
    
    std::vector<Data> sourceDataFrames;
    for (const auto& frame: frames) {
        sourceDataFrames.emplace_back(Data::zeros(frame.rows, frame.cols));
        for (int y = 0; y < frame.rows; y++) {
            for (int x = 0; x < frame.cols; x++) {
                sourceDataFrames.back()(y, x) = color_detector::detect(frame(y, x));
            }
        }
    }
    
    std::vector<Data> dataFrames;
    for (const auto& frame: sourceDataFrames) {
        dataFrames.emplace_back(Data::zeros(frame.rows, frame.cols));
        for (int y = 0; y < frame.rows; y++) {
            for (int x = 0; x < frame.cols; x++) {
                bool found = false;
                bool wasNone = false;
                bool wasNoData = false;
                for (int dx: dd) {
                    for (int dy: dd) {
                        int xx = x + dx;
                        int yy = y + dy;
                        if (goodPoint(frame, xx, yy)) {
                            auto color = frame(yy, xx);
                            if (!fixeds(yy, xx)) {
                                dataFrames.back()(y, x) = color;
                                found = true;
                                break;
                            }
                            wasNone |= (color == TYPE_NONE);
                            wasNoData |= (color == TYPE_NO_DATA);
                        }
                    }
                    if (found) break;
                }
                if (!found) {
                    if (wasNone)
                        dataFrames.back()(y, x) = TYPE_NONE;
                    else if (wasNoData)
                        dataFrames.back()(y, x) = TYPE_NO_DATA;
                    else
                        dataFrames.back()(y, x) = frame(y, x);
                }
            }
        }
    }
    
    dd = makeDd(dataFrames.size());
    
    for (int i = 0; i < dataFrames.size(); i++) {
        auto& frame = dataFrames[i];
        for (int y = 0; y < frame.rows; y++) {
            for (int x = 0; x < frame.cols; x++) {
                if (frame(y, x) == TYPE_NO_DATA) {
                    for (int di: dd) {
                        int ii = i + di;
                        if (ii < 0 || ii >= dataFrames.size()) continue;
                        const auto& frame2 = dataFrames[ii];
                        if (frame2(y, x) != TYPE_NO_DATA) {
                            frame(y, x) = frame2(y, x);
                        }
                    }
                }
                if (frame(y, x) == TYPE_NO_DATA)
                    frame(y, x) = TYPE_NONE;
            }
        }
    }
    
    return dataFrames;
}

RichData makeRichData(const Data& data) {
    cv::Mat padded;
    int m = 2 * cv::getOptimalDFTSize( data.rows );
    int n = 2 * cv::getOptimalDFTSize( data.cols ); 
    cv::copyMakeBorder(data, padded, 0, m - data.rows, 0, n - data.cols, cv::BORDER_CONSTANT, cv::Scalar::all(TYPE_NONE));

    cv::Mat planes[] = {cv::Mat_<float>(padded), cv::Mat::zeros(padded.size(), CV_32F)};
    cv::Mat complexI;
    cv::merge(planes, 2, complexI);

    cv::dft(complexI, complexI);

    for (int x = 0; x < complexI.cols; x++) {
        for (int y = 0; y < complexI.rows; y++) {
            if (x == 0 && y == 0) {
                complexI.at<cv::Vec2f>(y, x) = 0;
            } else {
                double dx = std::min(x, complexI.cols - x);
                double dy = std::min(y, complexI.rows - y);
                complexI.at<cv::Vec2f>(y, x) = complexI.at<cv::Vec2f>(y, x) / std::pow(std::hypot(dx, dy), 1);
            }
        }
    }

    cv::dft(complexI, complexI, cv::DFT_INVERSE + cv::DFT_SCALE);
    
    split(complexI, planes);
    
    //std::cout << planes[0].at<float>(0, 0) << " " << planes[1].at<float>(0, 0) << std::endl;

    cv::Rect roi(0, 0, data.cols, data.rows);
    RichData result;
    cv::Mat cropped(planes[0], roi);
    cropped.copyTo(result);    

    return result;
}

Data makeSlice(Data& data, int x0, int y0, cv::Vec2f dir) 
{
    const double ANGLE_RANGE = 0.05;
    const double MAX_ADD_SHIFT = 3;
    float angle = std::atan2(dir[1], dir[0]);
    
    Data result = Data::zeros(1, 100);

    for (int d = 0; d < 100; d++) {
        for (double da = -ANGLE_RANGE; da < ANGLE_RANGE + 1e-5; da += 0.01) {
            double aa = angle + da;
            double add_shift = da / ANGLE_RANGE * MAX_ADD_SHIFT;
            int xx = x0 - d * cos(aa) + add_shift * sin(angle);
            int yy = y0 - d * sin(aa) - add_shift * cos(angle);
            if (data(yy, xx) > result(0, d))
                result(0, d) = data(yy, xx);
        }
    }

    for (int d = 0; d < 100; d++) {
        for (double da = -ANGLE_RANGE; da < ANGLE_RANGE + 1e-5; da += 2*ANGLE_RANGE) {
            double aa = angle + da;
            double add_shift = da / ANGLE_RANGE * MAX_ADD_SHIFT;
            int xx = x0 - d * cos(aa) + add_shift * sin(angle);
            int yy = y0 - d * sin(aa) - add_shift * cos(angle);
            data(yy, xx) = TYPE_UNKNOWN;
        }
    }
    return result;
}

boost::optional<float> calcVelocity(const Data& slice1, const Data& slice2) {
    const int SHIFT = 20;
    cv::Rect roi(SHIFT, 0, slice1.cols - SHIFT, 1);
    cv::Mat cropped(slice1, roi);
    cv::Mat result;
    cv::matchTemplate(cropped, slice2, result, CV_TM_SQDIFF);
    double min, max;
    cv::Point minX;
    cv::minMaxLoc(result, &min, &max, &minX);
    
    /*
    std::cout << "cropped ";
    for (int x = 0; x < cropped.cols; x++) std::cout << (int)cropped.at<uchar>(0, x) << " ";
    std::cout << std::endl << "slice2 ";
    for (int x = 0; x < slice2.cols; x++) std::cout << (int)slice2.at<uchar>(0, x) << " ";
    std::cout << std::endl << "result ";
    for (int x = 0; x < result.cols; x++) std::cout << result.at<float>(0, x) << " ";
    std::cout << std::endl;

    
    std::cout << min << " " << max << " " << minX << std::endl;
    */

    if (min > cropped.cols * 3 / 4 || max <= 1.9 * min + 10 || minX.x < SHIFT / 3)
        return boost::none;
    return SHIFT - minX.x;
}

int main(int argc, char* argv[]) {
    std::cout << "Start loading images" << std::endl;
    auto images = loadImages(argv[1]);
    auto datas = convertToDatas(images);
    std::vector<RichData> richDatas;
    std::cout << "Start enriching data" << std::endl;
    for (const auto& data: datas)
        richDatas.push_back(makeRichData(data));

    std::cout << "Start calculate flow" << std::endl;
    Flow flow;
    
    cv::calcOpticalFlowFarneback(richDatas[0], richDatas[1], flow, 0.5, 8, 300, 2, 5, 1.3, cv::OPTFLOW_FARNEBACK_GAUSSIAN);

    for (int i = 2; i < richDatas.size(); i++) {
        Flow flow2;
        cv::calcOpticalFlowFarneback(richDatas[i-1], richDatas[i], flow2, 0.5, 8, 300, 2, 5, 1.3, cv::OPTFLOW_FARNEBACK_GAUSSIAN);
        flow += flow2;
    }
    
    colorize(flow, "flow");
    colorize(richDatas, "richData%02d");
    
    std::ofstream f("result.txt");
    for (const auto& point: POINTS) {
        std::string name = point.first;
        std::cout << "Start processing " << name << std::endl;
        int x = point.second.second;
        int y = point.second.first;
        auto dir = flow(y, x);

        std::vector<Data> thisDatas(datas.size());
        for (int i = 0; i < datas.size(); i++) {
            datas[i].copyTo(thisDatas[i]);
        }
        std::vector<Data> slices;
        for (int i = thisDatas.size() - 4; i < thisDatas.size(); i++) {
            std::cout << "Making slice " << i << std::endl;
            slices.push_back(makeSlice(thisDatas[i], x, y, dir));
        }
        
       
        colorize(thisDatas, name + "_data%02d");

        std::cout << "Slices: " << std::endl;
        for (int f = 0; f < slices.size(); f++) {
            const auto& slice = slices[f];
            std::cout << f << ": ";
            for (int x = 0; x < slice.cols; x++) std::cout << (int)slice(0, x) << " ";
            std::cout << std::endl;
        }
        
        double v = 0;
        int nv = 0;
        std::set<int> goodFrames;
        for (int i = 0; i < slices.size(); i++) {
            for (int j = i + 1; j < slices.size(); j++) {
                boost::optional<float> thisV = calcVelocity(slices[i], slices[j]);
                if (thisV) {
                    v += *thisV / (j - i);
                    nv++;
                    //std::cout << "v for " << i << " " << j << " " << *thisV << " = " << *thisV / (j - i) << std::endl;
                    goodFrames.insert(i);
                    goodFrames.insert(j);
                } else {
                    //std::cout << "v for " << i << " " << j << " --" << std::endl;
                }
            }
        }

        if (nv < 2) {
            f << name << " 0 0 0" << std::endl;
            std::cout << name << " 0 0 0" << std::endl;
            continue;
        }
        
        std::cout << "Good slices: " << std::endl;
        for (const auto& f: goodFrames) {
            const auto& slice = slices[f];
            std::cout << f << ": ";
            for (int x = 0; x < slice.cols; x++) std::cout << (int)slice(0, x) << " ";
            std::cout << std::endl;
        }
        
        v = v / nv;

        std::cout << "Detected v= " << v << std::endl;
        
        RichData result = RichData::zeros(slices[0].rows, slices[0].cols);
        RichData resultN = RichData::zeros(slices[0].rows, slices[0].cols);
        for (const auto& f: goodFrames) {
            const auto& slice = slices[f];
            int shift = v * (slices.size() - f - 0.5);
            int delta = ((slices.size() - f) / 2.0) + 1;
            double w = sqrt(1.0 * (f + 1) / slices.size()) / delta;
            std::cout << "Consider frame " << f << " shift " << shift << " w=" << w << " w*delta=" << w*delta << std::endl;
            for (int x = 0; x < slice.cols; x++) {
                for (int d = -delta; d <= delta; d++) {
                    int t = x + shift + d;
                    if (t < 0 || t >= slice.cols) continue;
                    if (slice(0, t) == TYPE_UNKNOWN) continue;
                    result(0, x) += slice(0, t) * w;
                    resultN(0, x) += w;
                }
            }
        }
        
        RichData finalResult = RichData::zeros(result.rows, result.cols);
        for (int x = 0; x < result.cols; x++) {
            if (resultN(0, x) > 1) {
                result(0, x) /= resultN(0, x);
                finalResult(0, x) = result(0, x) + 0.4;
            } else {
                finalResult(0, x) = TYPE_NONE;
            }
            std::cout << finalResult(0, x) << " ";
        }
        std::cout << std::endl;
        
        double start = 1e20;
        double end = 1e20;
        double type = TYPE_NONE;
        for (int x = 0; x < result.cols; x++) {
            double time = x / v;
            if (time - end > MERGE_THRESHOLD) break;
            if (finalResult(0, x) > TYPE_RAIN) {
                if (finalResult(0, x) > type) 
                    type = finalResult(0, x);
                if (time < start) { 
                    start = time; 
                    end = time; 
                }
                if (time > end) 
                    end = time;
            }
        }
        
        f << name << " " << type << " " << start*PERIOD << " " << end*PERIOD << std::endl;
        std::cout << name << " " << type << " " << start*PERIOD << " " << end*PERIOD << std::endl;
    }
    return 0;
}
