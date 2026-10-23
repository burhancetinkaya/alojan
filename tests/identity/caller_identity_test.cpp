#include "caller_identity.hpp"

#include <iostream>
#include <pjsua2.hpp>
#include <stdexcept>

namespace {
unsigned checks = 0;
void require(bool condition, const char *label) {
    ++checks;
    if (!condition)
        throw std::runtime_error(label);
}

alojan::CallerIdentity parse(const std::string &from, const std::string &headers,
                             const alojan::IdentityPolicy &policy,
                             const char *source = "127.0.0.1") {
    auto message = "INVITE sip:alojan@localhost SIP/2.0\r\n"
                   "Via: SIP/2.0/UDP 127.0.0.1:19001;branch=z9hG4bKunit\r\n"
                   "From: " +
                   from +
                   ";tag=unit\r\nTo: <sip:alojan@localhost>\r\n"
                   "Call-ID: synthetic-unit\r\nCSeq: 1 INVITE\r\n" +
                   headers + "Content-Length: 0\r\n\r\n";
    auto *pool = pjsua_pool_create("identity-test", 4096, 4096);
    require(pool != nullptr, "pool");
    pjsip_rx_data data{};
    data.tp_info.pool = pool;
    data.msg_info.msg = pjsip_parse_msg(pool, message.data(), message.size(), nullptr);
    auto ip = pj_str(const_cast<char *>(source));
    require(pj_sockaddr_init(pj_AF_INET(), &data.pkt_info.src_addr, &ip, 19001) == PJ_SUCCESS,
            "source address");
    require(data.msg_info.msg != nullptr, "SIP fixture parse");
    auto result = alojan::read_identity(data, policy);
    pj_pool_release(pool);
    return result;
}

void cases() {
    alojan::IdentityPolicy policy;
    policy.turkish_national = true;
    const std::string from = "<sip:+905550000001@example.invalid>";
    const std::string pai = "P-Asserted-Identity: <tel:+905550000002>\r\n";
    for (const auto &value : {"+905550000001", "00905550000001", "05550000001", "5550000001",
                              "905550000001", "+90-555-000-0001"}) {
        auto result = parse("<sip:" + std::string(value) + "@example.invalid>", "", policy);
        require(result.caller.e164 == "+905550000001", "Turkish canonicalization");
        require(result.caller.source == "from" && !result.trusted_source, "From is only a hint");
    }
    for (const auto &value :
         {"+90555000000", "+900550000001", "+0123456789", "+1", "112", "555ABC0001",
          "+905550000001%0A", "+905550000001%00", "+1234567890123456"}) {
        auto result = parse("<sip:" + std::string(value) + "@example.invalid>", "", policy);
        require(result.caller.e164.empty() && result.caller.status == "invalid",
                "invalid number rejected");
    }
    policy.turkish_national = false;
    require(parse("<sip:05550000001@example.invalid>", "", policy).caller.e164.empty(),
            "no implicit national prefix");
    require(parse("<tel:+1-202-555-0100>", "", policy).caller.e164 == "+12025550100",
            "international number syntax");
    require(parse("<tel:+2901234>", "", policy).caller.e164 == "+2901234",
            "short international syntax preserved");
    policy.turkish_national = true;
    require(parse("<tel:5550000001;phone-context=+90>", "", policy).caller.e164 == "+905550000001",
            "explicit Turkish context");
    require(parse("<tel:5550000001;phone-context=example.invalid>", "", policy).caller.e164.empty(),
            "unknown local context rejected");
    require(parse("<tel:+905550000001;ext=123>", "", policy).caller.e164.empty(),
            "extension not silently stripped");
    require(parse("<sip:+905550000001:secret@example.invalid>", "", policy).caller.e164.empty(),
            "password URI rejected");
    auto untrusted = parse(from, pai, policy);
    require(untrusted.caller.e164 == "+905550000001" && untrusted.pai_ignored,
            "untrusted PAI ignored");
    policy.add_trusted_ip("127.0.0.2");
    require(!parse(from, pai, policy).trusted_source, "Via cannot establish trust");
    policy.add_trusted_ip("127.0.0.1");
    auto trusted = parse(from, pai, policy);
    require(trusted.caller.e164 == "+905550000002" && trusted.caller.source == "pai" &&
                trusted.trusted_source,
            "trusted PAI precedence");
    require(parse(from, pai, policy, "127.0.0.3").caller.e164 == "+905550000001",
            "transport address controls trust");
    policy.from_first = true;
    require(parse(from, pai, policy).caller.e164 == "+905550000001", "configured From precedence");
    require(parse("<sip:unknown@example.invalid>", pai, policy).caller.e164 == "+905550000002",
            "trusted PAI fallback for unavailable From");
    policy.from_first = false;
    require(
        parse(from, pai + "P-Asserted-Identity: <sip:+905550000002@example.invalid>\r\n", policy)
                .caller.e164 == "+905550000002",
        "matching SIP and TEL assertions");
    require(parse(from,
                  "P-Asserted-Identity: \"Synthetic, Caller\" <sip:+905550000002@example.invalid>, "
                  "<tel:+905550000002>\r\n",
                  policy)
                    .caller.e164 == "+905550000002",
            "quoted comma list");
    require(
        parse(from, pai + "P-Asserted-Identity: <tel:+905550000003>\r\n", policy).caller.status ==
            "ambiguous",
        "conflicting PAI rejected");
    require(parse(from, "P-Asserted-Identity: garbage\r\n", policy).caller.status == "invalid",
            "malformed trusted PAI fails closed");
    require(parse(from, "P-Asserted-Identity: <tel:+905550000002> trailing\r\n", policy)
                    .caller.status == "invalid",
            "trailing junk rejected");
    for (const auto &value :
         {"id", "none;id", "user", "header", "future-extension", "ID;critical"}) {
        auto result = parse(from, pai + "Privacy: " + value + "\r\n", policy);
        require(result.caller.status == "withheld" && result.caller.e164.empty(), "privacy wins");
    }
    require(parse(from, pai + "Privacy: none\r\nPrivacy: id\r\n", policy).caller.e164.empty(),
            "duplicate privacy cannot downgrade");
    require(parse(from, pai + "Privacy: none\r\n", policy).caller.e164 == "+905550000002",
            "explicit no privacy");
    for (const auto &value : {"anonymous", "withheld", "restricted", "unknown", "unavailable"}) {
        auto result = parse("<sip:" + std::string(value) + "@example.invalid>", "", policy);
        require(result.caller.e164.empty(), "unavailable number not invented");
        require(result.caller.status != "invalid", "unavailable reason preserved");
    }
    require(parse("<sip:anonymous@anonymous.invalid>", pai, policy).caller.status == "anonymous",
            "PAI cannot reveal anonymous From");
    require(parse(from, "P-Asserted-Identity: <sip:anonymous@anonymous.invalid>\r\n", policy)
                    .caller.status == "anonymous",
            "anonymous PAI preserved");
    require(parse(from, "From: <sip:+905550000003@example.invalid>;tag=extra\r\n", policy)
                    .caller.status == "ambiguous",
            "duplicate From rejected");
    require(parse(from, "From: <sip:anonymous@anonymous.invalid>;tag=extra\r\n", policy)
                .caller.e164.empty(),
            "duplicate From cannot undo privacy");
    require(parse(from, "p-asserted-identity: <tel:+905550000002>\r\n", policy).caller.e164 ==
                "+905550000002",
            "case insensitive identity header");
    const std::string redirects =
        "Diversion: <sip:+905550000003@example.invalid>;reason=unconditional\r\n"
        "History-Info: <sip:+905550000004@example.invalid>;index=1, "
        "<sip:+905550000005@example.invalid>;index=1.1\r\n";
    auto forwarded = parse(from, pai + redirects, policy);
    require(forwarded.caller.e164 == "+905550000002" && forwarded.redirects.size() == 3,
            "redirects stay separate from caller");
    require(forwarded.redirects[0].e164 == "+905550000003" &&
                forwarded.redirects[0].source == "diversion" &&
                forwarded.redirects[2].e164 == "+905550000005" &&
                forwarded.redirects[2].source == "history-info",
            "redirect order and provenance retained");
    auto unknown_forwarded = parse("<sip:unknown@example.invalid>", redirects, policy);
    require(unknown_forwarded.caller.e164.empty(), "redirect is not a fallback caller");
    auto private_forwarded = parse(from, pai + redirects + "Privacy: id\r\n", policy);
    require(private_forwarded.redirects.empty(), "private redirect metadata suppressed");
    auto private_redirect =
        parse(from, "Diversion: <sip:+905550000003@example.invalid>;privacy=full\r\n", policy);
    require(private_redirect.redirects[0].e164.empty() &&
                private_redirect.redirects[0].status == "withheld",
            "Diversion privacy respected");
    policy.trusted_ips.clear();
    auto spoofed = parse(from, redirects, policy);
    require(spoofed.redirects.empty() && spoofed.redirects_ignored,
            "untrusted redirects not retained");
    require(parse(from, "Privacy: id\r\n", policy).caller.status == "withheld",
            "privacy respected without trusted operator");
    const auto log = forwarded.log_fields();
    for (const auto &forbidden : {"90555", "example.invalid", "Synthetic", "sip:", "tel:"})
        require(log.find(forbidden) == std::string::npos, "PII absent from log");
    require(log.find("caller_number=redacted") != std::string::npos, "number fully redacted");
    policy.add_trusted_ip("127.0.0.1");
    std::string excessive;
    for (int i = 0; i < 17; ++i)
        excessive += pai;
    require(parse(from, excessive, policy).caller.status == "invalid", "bounded header count");
    require(parse(from, "P-Asserted-Identity: " + std::string(1100, 'x') + "\r\n", policy)
                    .caller.status == "invalid",
            "bounded header size");
    for (const auto &bad : {"localhost", "127.0.0.1:5060", "127.0.0.0/8", "127.0.0.1evil", "*"}) {
        bool rejected = false;
        try {
            policy.add_trusted_ip(bad);
        } catch (const std::invalid_argument &) {
            rejected = true;
        }
        require(rejected, "trust configuration rejects nonliteral IP");
    }
    require(trusted.caller.e164 == "+905550000002", "identity owns data beyond receive pool");
}
} // namespace

int main() {
    try {
        pj_log_set_level(0);
        pj::Endpoint endpoint;
        endpoint.libCreate();
        pj::EpConfig config;
        config.logConfig.level = 0;
        config.logConfig.consoleLevel = 0;
        config.logConfig.msgLogging = false;
        endpoint.libInit(config);
        cases();
        endpoint.libDestroy();
        std::cout << "identity_checks=" << checks << " passed\n";
        return 0;
    } catch (const std::exception &error) {
        std::cerr << "identity_test_failed=" << error.what() << '\n';
    } catch (const pj::Error &) {
        std::cerr << "identity_test_failed=pjsip_init\n";
    }
    return 1;
}
