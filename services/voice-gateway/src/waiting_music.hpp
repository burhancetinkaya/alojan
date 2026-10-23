#pragma once

#include <array>
#include <cstdint>

namespace alojan {
// Original six-second instrumental loop, prepared before media callbacks run.
class WaitingMusic {
  public:
    WaitingMusic();
    void render(char *pcm, std::uint64_t frame) const noexcept;

  private:
    std::array<std::array<char, 320>, 300> frames_{};
};
} // namespace alojan
