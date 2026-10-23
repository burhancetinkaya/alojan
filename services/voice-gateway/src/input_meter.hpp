#pragma once

#include <atomic>
#include <cstdint>
#include <cstring>
#include <pjsua2.hpp>

// Media callbacks update counters only: no disk, network, logging or allocation.
class InputMeter : public pj::AudioMediaPort {
  public:
    static constexpr unsigned rate_hz = 16000;
    static constexpr unsigned samples_per_frame = rate_hz / 50;
    std::atomic<unsigned long> frames{0}, samples{0}, bad_frames{0}, nonzero_samples{0};
    void onFrameReceived(pj::MediaFrame &frame) override {
        // PJMEDIA sends empty heartbeats while a port has no transmitter (including teardown).
        if (frame.type == PJMEDIA_FRAME_TYPE_NONE && frame.buf.empty())
            return;
        if (frame.type != PJMEDIA_FRAME_TYPE_AUDIO ||
            frame.buf.size() != samples_per_frame * sizeof(std::int16_t)) {
            bad_frames.fetch_add(1, std::memory_order_relaxed);
            return;
        }
        unsigned long nonzero = 0;
        for (std::size_t i = 0; i + 1 < frame.buf.size(); i += 2) {
            std::int16_t sample;
            std::memcpy(&sample, frame.buf.data() + i, sizeof(sample));
            if (sample > 100 || sample < -100)
                ++nonzero;
        }
        nonzero_samples.fetch_add(nonzero, std::memory_order_relaxed);
        samples.fetch_add(samples_per_frame, std::memory_order_relaxed);
        frames.fetch_add(1, std::memory_order_relaxed);
    }
};
