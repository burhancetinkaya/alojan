#include "input_meter.hpp"
#include <iostream>
#include <stdexcept>

void require(bool value, const char *message) {
    if (!value)
        throw std::runtime_error(message);
}

int main() {
    pj::Endpoint endpoint;
    endpoint.libCreate();
    int result = 0;
    try {
        InputMeter meter;
        pj::MediaFrame frame;
        frame.type = PJMEDIA_FRAME_TYPE_NONE;
        meter.onFrameReceived(frame);
        require(meter.bad_frames == 0 && meter.samples == 0 && meter.frames == 0,
                "empty PJMEDIA heartbeat is not malformed PCM");
        frame.type = PJMEDIA_FRAME_TYPE_AUDIO;
        meter.onFrameReceived(frame);
        require(meter.bad_frames == 1, "empty AUDIO frame is still invalid");
        frame.buf.resize(639);
        meter.onFrameReceived(frame);
        require(meter.bad_frames == 2, "misaligned AUDIO frame is invalid");
        frame.buf.assign(640, 0);
        meter.onFrameReceived(frame);
        require(meter.frames == 1 && meter.samples == 320 && meter.nonzero_samples == 0,
                "silent AUDIO frame counts as received PCM");
        frame.buf[0] = 127;
        meter.onFrameReceived(frame);
        require(meter.frames == 2 && meter.samples == 640 && meter.nonzero_samples == 1,
                "valid nonzero PCM reaches the meter");
        frame.type = PJMEDIA_FRAME_TYPE_NONE;
        meter.onFrameReceived(frame);
        require(meter.bad_frames == 3, "NONE with a payload is not a valid heartbeat");
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n';
        result = 1;
    }
    endpoint.libDestroy();
    return result;
}
