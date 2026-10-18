# Paper V3 implementation

Approved source: [Marco Polo in Paper](https://app.paper.design/file/01M55Z1GDRDK8E0XJMJE99EECZ/p-1-0), artboards **V3 · Shared visual system**, **V3 · Live — Finding keys**, and **V3 · iOS — Ready**.

Both frontends bundle Instrument Sans locally: regular 400, medium 500, semibold 600. Web uses the variable WOFF2; native uses static TTF faces with Dynamic Type. Both retain the SIL Open Font License. Canvas `#F6F6F3`, ink `#202124`, accent `#1559D6`, secondary `#62666D`, separators `#DDDFDB`, success `#356B55`. The existing paired mark keeps its geometry.

Web: 48px page title, 112px guiding distance, 27px direction, 56px desktop column gap, 352px guidance column. Active navigation is underlined. The map keeps one rounded surface; guidance and Objects use open layouts. Narrow layouts retain readable controls and stack the map above guidance. Objects follows the same system with a larger selected photo and quieter rows. All existing disconnected, missing-media, pending-command, empty, found and Photon states remain functional.

iOS: 54pt scalable state heading, 28pt horizontal padding, open hardware rows, 96pt circular Start/Stop control. Native OS status bars and SF Symbols stay native; app text uses Instrument Sans. ViewThatFits and scrolling accommodate large text or long output names. The panel uses `ios/Marco/App/AppModel.swift` and its ARKit pipeline, not a second camera session.

The UI refresh changes no server message formats. The `/v1` server needs a dashboard adapter before the web API mode can use it; see [fastapi-handoff.md](fastapi-handoff.md).
