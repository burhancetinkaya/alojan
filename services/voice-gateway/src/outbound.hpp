#pragma once
#include <chrono>
#include <filesystem>
#include <fstream>
#include <optional>
#include <regex>
#include <stdexcept>
#include <string>

namespace alojan {
// Private, single-writer node spool. Renaming pending to running consumes the right
// to originate. A gateway restart may close the old request, never originate it again.
struct OutboundRequest {
    std::filesystem::path root;
    std::string id, caller, destination;
    unsigned ring_seconds{}, wait_seconds{};
    std::string result;
    bool confirmed = false;

    void report(const std::string &status) const {
        const auto path = root / (id + ".status");
        const auto temp = root / (id + ".tmp");
        std::ofstream stream;
        stream.exceptions(std::ios::failbit | std::ios::badbit);
        stream.open(temp);
        stream << status << '\n';
        stream.close();
        if (status == "answered")
            std::ofstream(root / (id + ".answered")).close();
        std::filesystem::rename(temp, path);
    }

    static OutboundRequest read(const std::filesystem::path &root) {
        OutboundRequest request;
        request.root = root;
        std::ifstream data(root / "running");
        if (!(data >> request.id >> request.caller >> request.destination >> request.ring_seconds >>
              request.wait_seconds) ||
            !std::regex_match(request.id, std::regex("[0-9a-f]{32}")) ||
            !std::regex_match(request.caller, std::regex("\\+90850[0-9]{7}")) ||
            !std::regex_match(request.destination, std::regex("\\+90[2345][0-9]{9}")) ||
            request.ring_seconds < 1 || request.ring_seconds > 120 || request.wait_seconds > 30)
            throw std::runtime_error("invalid private outbound request");
        return request;
    }

    void finish(const std::string &status) const {
        report(status);
        std::filesystem::remove(root / "running");
    }
};
} // namespace alojan
