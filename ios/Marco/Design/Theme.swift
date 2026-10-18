import SwiftUI

enum Theme {
    static let blue = Color(red: 21 / 255, green: 89 / 255, blue: 214 / 255)
    static let ink = Color(red: 32 / 255, green: 33 / 255, blue: 36 / 255)
    static let canvas = Color(red: 246 / 255, green: 246 / 255, blue: 243 / 255)
    static let secondary = Color(red: 98 / 255, green: 102 / 255, blue: 109 / 255)
    static let border = Color(red: 221 / 255, green: 223 / 255, blue: 219 / 255)
    static let green = Color(red: 53 / 255, green: 107 / 255, blue: 85 / 255)
    static let amber = Color(red: 153 / 255, green: 95 / 255, blue: 19 / 255)

    enum Weight: String { case regular = "Regular", medium = "Medium", semibold = "SemiBold" }
    static func font(_ size: CGFloat, _ weight: Weight = .regular, relativeTo style: Font.TextStyle = .body) -> Font {
        .custom("InstrumentSans-" + weight.rawValue, size: size, relativeTo: style)
    }
}

struct MarcoPoloMark: View {
    var body: some View {
        GeometryReader { proxy in
            let scale = min(proxy.size.width, proxy.size.height) / 40
            Path { p in
                p.move(to: CGPoint(x: 5, y: 25))
                p.addLine(to: CGPoint(x: 5, y: 13))
                p.addCurve(to: CGPoint(x: 15, y: 3), control1: CGPoint(x: 5, y: 7.477), control2: CGPoint(x: 9.477, y: 3))
                p.addLine(to: CGPoint(x: 23, y: 3)); p.addLine(to: CGPoint(x: 23, y: 10))
                p.addLine(to: CGPoint(x: 15, y: 10))
                p.addCurve(to: CGPoint(x: 12, y: 13), control1: CGPoint(x: 13.343, y: 10), control2: CGPoint(x: 12, y: 11.343))
                p.addLine(to: CGPoint(x: 12, y: 25)); p.closeSubpath()
                p.move(to: CGPoint(x: 35, y: 15)); p.addLine(to: CGPoint(x: 35, y: 27))
                p.addCurve(to: CGPoint(x: 25, y: 37), control1: CGPoint(x: 35, y: 32.523), control2: CGPoint(x: 30.523, y: 37))
                p.addLine(to: CGPoint(x: 17, y: 37)); p.addLine(to: CGPoint(x: 17, y: 30))
                p.addLine(to: CGPoint(x: 25, y: 30))
                p.addCurve(to: CGPoint(x: 28, y: 27), control1: CGPoint(x: 26.657, y: 30), control2: CGPoint(x: 28, y: 28.657))
                p.addLine(to: CGPoint(x: 28, y: 15)); p.closeSubpath()
            }
            .fill(Theme.blue)
            .scaleEffect(scale, anchor: .topLeading)
        }
        .accessibilityHidden(true)
    }
}
