#include "prepared_audio.hpp"
#include <array>
#include <cassert>
#include <cstring>

int main() {
    std::string pcm;
    for (unsigned i = 0; i < 160 * 5; ++i) {
        pcm += static_cast<char>(0xe8);
        pcm += static_cast<char>(0x03);
    }
    std::array<char, 320> frame{};
    alojan::WaitingPlayback first, other;
    first.start();
    frame.fill(0x12);
    first.blend_response(pcm, frame.data());
    assert(frame.front() == 0x12 && frame.back() == 0x12 && !first.active());
    assert(first.frames() == 0 && !first.completed());
    first.start();
    other.start();
    assert(first.render(pcm, frame.data()));
    assert(first.frames() == 1 && other.frames() == 0);
    const std::int16_t response_sample = -1000;
    for (unsigned i = 0; i < 160; ++i)
        std::memcpy(frame.data() + i * 2, &response_sample, 2);
    first.blend_response(pcm, frame.data());
    std::int16_t start, end;
    std::memcpy(&start, frame.data(), 2);
    std::memcpy(&end, frame.data() + 318, 2);
    assert(start == 1000 && end == -1000);
    std::int16_t middle;
    std::memcpy(&middle, frame.data() + 78, 2);
    assert(middle == -1000); // By 5 ms the original response frame is unchanged.
    assert(!first.active() && !first.completed());
    assert(!first.render(pcm, frame.data())); // Old audio never resumes.
    assert(first.frames() == 2);
    for (unsigned i = 0; i < 5; ++i)
        assert(other.render(pcm, frame.data()));
    assert(other.completed() && other.frames() == 5);
    first.reset();
    assert(first.frames() == 0 && !first.active() && !first.completed());
    first.start();
    first.stop();
    assert(!first.render(pcm, frame.data()));
}
