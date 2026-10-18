import Foundation

// The wire formats of docs/INTERFACES.md. Property names are the wire keys, so each struct reads 1:1 against the
// contract. server/tests/test_ios_contract.py feeds what this file encodes to the real server.
// Every phone -> server message carries session_id, so the server files it into the right recording.

// MARK: - Phone to server

/// §3.1 `meta` part of POST /v1/frames.
struct FrameMeta: Codable, Equatable {
    var session_id: String
    var map_id: String
    var frame_id: Int
    var t_device: Double             // ARFrame.timestamp
    var t_wall: String               // ISO-8601 UTC
    var tracking: String             // frames are only sent while this is "normal"
    var camera_transform: [Float]    // 16, column-major, camera to world
    var intrinsics: [Float]          // 9, column-major, for image_resolution
    var image_resolution: [Int]      // [1920, 1440]
    var jpeg_scale: Double           // 0.5: the JPEG is 960x720
}

/// §3.2, 10 per second.
struct PoseMsg: Codable, Equatable {
    var type = "pose"
    var session_id: String
    var map_id: String
    var t_device: Double
    var camera_transform: [Float]
    var head_yaw_deg: Double         // listener yaw in the world (Geo.headingDeg convention)
    var head_source: String          // "fusion" (AirPods + ARKit) or "phone"
}

struct Joint: Codable, Equatable {
    var name: String                 // HandJoints.names
    var x: Double                    // Vision normalized, orientation .up (sensor frame), origin bottom-left
    var y: Double
    var conf: Double
}

/// §3.2, 15 per second while Vision sees a hand.
struct HandMsg: Codable, Equatable {
    var type = "hand"
    var session_id: String
    var map_id: String
    var t_device: Double
    var camera_transform: [Float]
    var vision_orientation = "up"
    var chirality: String            // "left" | "right" | "unknown"
    var joints: [Joint]              // 21, in HandJoints.names order
    var depth_patches_f16_b64: String
    var conf_patches_u8_b64: String
    var patch = HandJoints.patch
}

/// §3.2, 10 per second while guiding: what the user hears, for the dashboard radar.
struct GuidanceMsg: Codable, Equatable {
    var type = "guidance"
    var session_id: String
    var item_id: String?
    var phase: String                // Phase.rawValue
    var rel_azimuth_deg: Double      // relative to the head: 0 ahead, +90 right
    var distance_m: Double           // horizontal, chest to item
}

/// §3.2: what the wearer hears, for the dashboard. One per sound, the moment it starts; the server only relays it.
struct SoundMsg: Codable, Equatable {
    var type = "sound"
    var session_id: String
    var t_device: Double
    var cue: String                  // beep | ding | tone_on | tone_off | say | label | blip | silence
    var source: String               // beacon | voice
    var anchor: String               // item | room | ahead
    var az_deg: Double               // relative to the head: 0 ahead, +90 right, ±180 behind
    var el_deg: Double               // + up
    var distance_m: Double           // ear to source
    var muffled: Bool?
    var text: String?
    var duration_s: Double?
    var audio_url: String?
}

/// §3.2: where each audible source is now, relative to the head; 10/s while anything is audible, then one with both
/// sources absent when it goes quiet.
struct SoundFieldMsg: Codable, Equatable {
    struct Source: Codable, Equatable {
        var az_deg: Double
        var el_deg: Double
        var distance_m: Double
        var muffled: Bool?           // beacon
        var anchor: String?          // voice
    }
    var type = "sound_field"
    var session_id: String
    var t_device: Double
    var head_yaw_deg: Double
    var beacon: Source?
    var voice: Source?
}

/// §3.2: the phone's answer to a dashboard `command` (status accepted | applied | rejected, with a reason).
struct CommandAckMsg: Codable, Equatable {
    var type = "command_ack"
    var session_id: String
    var command_id: String
    var status: String
    var reason: String?
}

/// §3.2 queries: kind find (name), what_is_this, set_place (name "door").
struct QueryMsg: Codable, Equatable {
    var type = "query"
    var session_id: String
    var query_id: String
    var kind: String
    var name: String?
}

/// §3.4 map lifecycle: event relocalized | new_map | saved.
struct MapMsg: Codable, Equatable {
    var type = "map"
    var session_id: String
    var event: String
    var map_id: String
}

// MARK: - Server to phone (§4)

struct FindAnswer: Codable, Equatable {
    var query_id: String?
    var found: Bool
    var item_id: String?
    var name: String?
    var position: [Float]?
    var surface: String?
    var seen_ago_s: Double?
    var confidence: Double?
    var state: String?
    var reason: String?              // not_registered | never_seen | not_where_last_seen
    var last_position: [Float]?
}

struct WhatAnswer: Codable, Equatable {
    var query_id: String?
    var status: String               // known | unknown | no_touch
    var item_id: String?
    var name: String?
    var label_text: String?
    var label_audio_url: String?
    var touch_id: String?
}

struct SetPlaceAnswer: Codable, Equatable {
    var query_id: String?
    var name: String?
    var ok: Bool?
}

struct TouchMsg: Codable, Equatable {
    var touch_id: String
    var item_id: String?             // nil: an unknown thing is being touched
    var name: String?
    var position: [Float]?
    var t_device: Double?
}

struct TouchEndMsg: Codable, Equatable {
    var touch_id: String
}

struct HandProximityMsg: Codable, Equatable {
    var item_id: String
    var distance_m: Double
}

struct WorldEventMsg: Codable, Equatable {
    var kind: String                 // seen | moved | put_down | picked_up | missing | left_behind | label_added
    var item_id: String
    var name: String
    var position: [Float]?
    var from_position: [Float]?
    var surface: String?
    var t_wall: String?
}

struct LabelReadyMsg: Codable, Equatable {
    var item_id: String
    var name: String
    var label_text: String?
    var label_audio_url: String?
}

struct ServerErrorMsg: Codable, Equatable {
    var detail: String
    var for_type: String?
}

/// One entry of GET /v1/items.
struct ItemInfo: Codable, Equatable {
    var item_id: String
    var name: String
    var position: [Float]?
    var surface: String?
    var state: String?
    var label_text: String?
    var label_audio_url: String?
}

/// Reply of POST /v1/items (§3.3).
struct RegistrationReply: Codable, Equatable {
    var item_id: String?
    var quality: String              // ok | retake
    var reason: String?
}

/// §4: Find or Stop from the dashboard. Find carries the exact item (no name lookup) and where it is.
struct CommandMsg: Codable, Equatable {
    var command_id: String
    var session_id: String
    var action: String               // find | stop
    var item_id: String?
    var name: String?
    var position: [Float]?
    var surface: String?
    var expires_wall: String?        // ISO-8601 UTC; a late command is rejected, never started
}

enum ServerMessage: Equatable {
    case find(FindAnswer)
    case whatIsThis(WhatAnswer)
    case setPlace(SetPlaceAnswer)
    case touch(TouchMsg)
    case touchEnd(TouchEndMsg)
    case handProximity(HandProximityMsg)
    case event(WorldEventMsg)
    case labelReady(LabelReadyMsg)
    case error(ServerErrorMsg)
    case command(CommandMsg)
    case other(String)               // a type this app doesn't handle yet

    private struct Head: Decodable {
        let type: String
        let kind: String?
    }

    static func decode(_ data: Data) throws -> ServerMessage {
        let d = JSONDecoder()
        let h = try d.decode(Head.self, from: data)
        switch h.type {
        case "answer":
            switch h.kind {
            case "find": return .find(try d.decode(FindAnswer.self, from: data))
            case "what_is_this": return .whatIsThis(try d.decode(WhatAnswer.self, from: data))
            case "set_place": return .setPlace(try d.decode(SetPlaceAnswer.self, from: data))
            default: return .other("answer/\(h.kind ?? "?")")
            }
        case "touch": return .touch(try d.decode(TouchMsg.self, from: data))
        case "touch_end": return .touchEnd(try d.decode(TouchEndMsg.self, from: data))
        case "hand_proximity": return .handProximity(try d.decode(HandProximityMsg.self, from: data))
        case "event": return .event(try d.decode(WorldEventMsg.self, from: data))
        case "label_ready": return .labelReady(try d.decode(LabelReadyMsg.self, from: data))
        case "error": return .error(try d.decode(ServerErrorMsg.self, from: data))
        case "command": return .command(try d.decode(CommandMsg.self, from: data))
        default: return .other(h.type)
        }
    }
}

enum HandJoints {
    static let patch = 9
    /// Vision's 21 hand joints, in the order the server expects (server/marco/touch.py JOINTS).
    static let names = ["wrist", "thumbCMC", "thumbMP", "thumbIP", "thumbTip", "indexMCP", "indexPIP", "indexDIP", "indexTip",
                        "middleMCP", "middlePIP", "middleDIP", "middleTip", "ringMCP", "ringPIP", "ringDIP", "ringTip",
                        "littleMCP", "littlePIP", "littleDIP", "littleTip"]
}

enum Clock {
    /// ISO-8601 UTC with milliseconds, e.g. 2026-10-17T15:04:05.123Z.
    static func wall(_ date: Date = Date()) -> String {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        f.timeZone = TimeZone(identifier: "UTC")
        return f.string(from: date)
    }
}
