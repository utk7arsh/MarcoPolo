import Foundation

enum VoiceInputStatus: Hashable {
    case off, starting, listening, permissionDenied, unavailable

    var label: String {
        switch self {
        case .off: return "Off"
        case .starting: return "Checking access"
        case .listening: return "Listening"
        case .permissionDenied: return "Access disabled"
        case .unavailable: return "Unavailable"
        }
    }
    var help: String? {
        switch self {
        case .permissionDenied:
            return "Voice commands are off. Allow microphone and speech recognition in iPhone Settings, then restart the camera."
        case .unavailable:
            return "Voice commands are unavailable. Stop and restart the camera to try again."
        default: return nil
        }
    }
}

/// A stable, human-readable snapshot, separate from sensor telemetry and UIKit speech delivery.
/// Only meaningful changes generate announcements; reading status always uses the latest snapshot.
struct AccessibleControlStatus: Hashable {
    var phase: CaptureControl.Phase = .ready
    var message: String?
    var lidarAvailable = true
    var serverConfigured = false
    var serverConnected = false
    var audio = AudioRouteState()
    var audioProblem: String?
    var voice: VoiceInputStatus = .off
    var tracking = "not started"

    var capturing: Bool { phase == .starting || phase == .running }
    var waitingForServer: Bool { capturing && !serverConnected }

    var cameraActionHint: String {
        switch phase {
        case .denied: return "Opens iPhone Settings so you can allow camera access."
        case .unsupported: return "Requires an iPhone with LiDAR."
        case .permission: return "Respond to the iPhone camera permission alert."
        case .running, .starting: return "Stops capture, listening, and navigation audio."
        default: return "Starts the camera. Two-finger double-tap also starts or stops the camera."
        }
    }

    var cameraDescription: String {
        if phase == .denied {
            return "Camera access is off. " + (message ?? "Open iPhone Settings to allow camera access.")
        }
        if phase == .interrupted { return message ?? "Camera interrupted. Start the camera again when ready." }
        let state: String
        switch phase {
        case .ready: state = "Camera is off. Ready to start."
        case .permission: state = "Waiting for camera permission. Respond to the iPhone permission alert."
        case .starting: state = "Starting camera."
        case .running: state = "Camera running."
        case .denied: state = "Camera access is off."
        case .unsupported: state = "This device does not support LiDAR. A LiDAR-capable iPhone is required."
        case .interrupted: state = "Camera interrupted."
        case .failed: state = "Camera could not continue. Try starting the camera again."
        }
        return [state, message].compactMap { $0 }.joined(separator: " ")
    }

    var serverDescription: String {
        if serverConnected { return "Server connected." }
        if !serverConfigured { return "Server address is missing. Open Connection settings to add it." }
        if capturing { return "Server connecting. If it does not connect, check Wi-Fi, Tailscale, and the server address." }
        return "Server not connected. Start the camera to connect."
    }

    var audioDescription: String {
        if audio.external { return "Audio output: \(audio.name). \(audio.spatialLabel)." }
        if audio.name == "Unknown" { return "Audio output is not known yet." }
        return "Audio output: iPhone. Connect headphones for directional audio."
    }

    var trackingHelp: String? {
        switch tracking {
        case "normal", "not started": return nil
        case "limited: initializing": return "Position tracking is starting."
        case "limited: relocalizing": return "Finding your saved room. Move the phone slowly."
        case "limited: moving too fast": return "Position tracking is limited. Move the phone more slowly."
        case "limited: too few features": return "Position tracking is limited. Point the camera toward nearby objects in better light."
        default: return "Position tracking is unavailable. Pause and let the camera find the room."
        }
    }

    var summary: String {
        [cameraDescription, lidarAvailable ? "LiDAR available." : "LiDAR not supported.",
         serverDescription, audioDescription, audioProblem,
         voice.help ?? "Voice commands: \(voice.label.lowercased()).",
         phase == .running ? trackingHelp : nil]
            .compactMap { $0 }.joined(separator: " ")
    }

    /// Called after UI changes settle. No initial narration or focus changes: VoiceOver owns navigation.
    func announcement(since previous: Self) -> String? {
        var lines: [String] = []
        if phase != previous.phase, phase != .permission {
            lines.append(phase == .ready && previous.capturing ? "Camera stopped." : cameraDescription)
            if phase == .running && !serverConnected { lines.append(serverDescription) }
        } else if message != previous.message, let message {
            lines.append(message)
        }
        if capturing && serverConnected != previous.serverConnected {
            lines.append(serverConnected ? "Server connected." : "Server disconnected. Check Wi-Fi and Tailscale.")
        }
        if audio != previous.audio, previous.audio.name != "Unknown" {
            // The OS spatial-audio flag is informational; our HRTF renderer does not require it to be on.
            if audio.name != previous.audio.name || audio.external != previous.audio.external {
                lines.append(previous.audio.external && !audio.external
                    ? "Headphones disconnected. \(audioDescription)" : audioDescription)
            }
        }
        if capturing && audioProblem != previous.audioProblem, let audioProblem { lines.append(audioProblem) }
        if capturing && voice != previous.voice {
            if let help = voice.help { lines.append(help) }
            else if previous.voice.help != nil && voice == .listening { lines.append("Voice commands are listening again.") }
        }
        if phase == .running && previous.phase == .running {
            if previous.tracking == "normal", let trackingHelp { lines.append(trackingHelp) }
            else if tracking == "normal", previous.trackingHelp != nil,
                    !["limited: initializing", "limited: relocalizing"].contains(previous.tracking) {
                lines.append("Position tracking restored.")
            }
        }
        return lines.isEmpty ? nil : lines.joined(separator: " ")
    }
}
