import Foundation

/// Rates and tunables from docs/INTERFACES.md. Things to change on the device live in UserDefaults (debug screen).
enum Config {
    /// The server Mac, reached over Tailscale: `tailscale serve` there gives an https URL (see server/README.md).
    static var serverURL: URL? {
        get { UserDefaults.standard.string(forKey: "serverURL").flatMap { URL(string: $0) } }
        set { UserDefaults.standard.set(newValue?.absoluteString, forKey: "serverURL") }
    }

    static let frameHz = 1.0
    static let poseHz = 10.0
    static let handHz = 15.0
    static let guidanceMsgHz = 10.0
    static let jpegScale = 0.5           // 1920x1440 sensor image -> 960x720 JPEG
    static let jpegQuality = 0.8
    static let earAboveChestM: Float = 0.45
    static let relocalizeTimeoutS = 30.0
    static let mapSaveIntervalS = 30.0
    static let demoItems = ["keys", "wallet", "mug", "bottle"]

    /// CoreMotion's yaw grows turning left; our headings grow turning right, hence -1. Hour-one test: turn your
    /// head right with the AirPods in; "head yaw" on the debug screen must go up. If it goes down, flip the switch.
    static var airpodsYawSign: Double {
        UserDefaults.standard.bool(forKey: "flipAirpodsYaw") ? 1 : -1
    }
}
