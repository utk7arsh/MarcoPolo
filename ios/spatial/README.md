# Spatial audio experiments

Mac test tools for Marco Polo's iPhone audio pipeline. Run commands from the
repository root on macOS with Xcode's Swift tools installed.

These tools compile the actual classes in `../Marco/Audio/` and the portable
iOS core. There is no second copy of the production audio engine. The iPhone
still owns ARKit positioning, head fusion and live guidance; the server supplies
world-space targets and touch events.

## Automated checks (silent)

```sh
sh ios/spatial/check-render.sh       # Apple offline HRTF renderer
sh ios/spatial/check-simulation.sh   # deterministic scripted trajectory checks
sh ios/spatial/check-airpods.sh --build-only
sh ios/spatial/check-options.sh      # withdrawn mode refuses playback in script and app
sh ios/check.sh                 # production portable Swift checks
```

Build output stays in ignored `ios/spatial/build/`. No package installation is needed.
The scripts work when invoked from another directory as well.

## AirPods checks (physical hardware)

Select the AirPods as the Mac's sound output and wear both earbuds. Allow Motion
permission for the helper when prompted. Listening uses a 35% app mixer gain,
does not change system volume, and does not record the microphone or use a server.

```sh
sh ios/spatial/check-airpods.sh              # 12-second motion sample check
sh ios/spatial/check-airpods.sh --listen     # timed left/right/front/back voice tour
sh ios/spatial/check-airpods.sh --front-back # timed A/B tour with live head yaw
```

The tours advance on a timer to compare sounds. They do **not** track walking,
hand reach or touch. A Bluetooth output is required before listening starts.
The helper waits for fresh motion in the front/back test and pauses audio when
motion becomes stale. That test's stage timer continues through motion loss.

## Scripted approach (explicit simulation only)

The wearer rejected the former `--guidance` demo because it moved closer and
claimed a touch even while they stayed still. That option now exits without
audio. The old sequence is preserved only for explicit sound demonstrations:

```sh
sh ios/spatial/check-airpods.sh --simulate-approach
```

Stay seated. Only head yaw comes from hardware. Distance, hand proximity and
touch are generated on a timer; an alignment timeout also advances the script.
An internal alignment flag does not establish physical head movement. This mode
cannot validate navigation, arrival, touch or movement-dependent feedback.

## Current evidence

The wearer found left/right clear. Front/back, perceived distance, physical yaw
sign and world anchoring remain unresolved. Headphone motion supplies orientation,
not walking position. Real walking and reach require the chest-mounted iPhone's
ARKit pose and live hand/touch inputs; no developer iPhone was available to this
Mac in the latest device check.

See [verification notes](VERIFICATION.md) for measured results, the immediate
item-voice positioning fix, Apple references and remaining device checks.
