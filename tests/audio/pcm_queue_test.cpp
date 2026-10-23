#include "speech_bridge.hpp"
#include <iostream>
#include <stdexcept>

void require(bool value, const char *message) {
    if (!value)
        throw std::runtime_error(message);
}

int main() {
    try {
        alojan::PcmQueue<sizeof(std::uint64_t), 4> queue;
        std::uint64_t value = 0;
        require(!queue.pop(reinterpret_cast<char *>(&value)), "empty queue must not read");
        for (value = 0; value < 4; ++value)
            require(queue.push(reinterpret_cast<char *>(&value)),
                    "capacity unexpectedly exhausted");
        require(!queue.push(reinterpret_cast<char *>(&value)),
                "overflow must reject without overwrite");
        for (std::uint64_t expected = 0; expected < 4; ++expected) {
            require(queue.pop(reinterpret_cast<char *>(&value)), "queued frame lost");
            require(value == expected, "frame reordered or overwritten");
        }
        std::atomic<bool> corrupted{false};
        std::thread producer([&] {
            for (std::uint64_t i = 0; i < 100000; ++i)
                while (!queue.push(reinterpret_cast<const char *>(&i)))
                    std::this_thread::yield();
        });
        std::thread consumer([&] {
            for (std::uint64_t i = 0; i < 100000; ++i) {
                std::uint64_t received;
                while (!queue.pop(reinterpret_cast<char *>(&received)))
                    std::this_thread::yield();
                if (received != i)
                    corrupted.store(true);
            }
        });
        producer.join();
        consumer.join();
        require(!corrupted.load() && queue.empty(), "concurrent wraparound corrupted PCM");
        std::cout << "bounded PCM queue passed\n";
        return 0;
    } catch (const std::exception &error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
