# E2B and browser deployment validation

## Native E2B integration

[PR #1](https://github.com/OpulentiaAI/cua-spaces/pull/1) enabled the existing
E2B provider in the Tauri app, bundled CLI, daemon and live launcher. It also
fixed a Linux tray-menu startup deadlock. Those changes are already on main.

The subsequent live validation established:

- The E2B control-plane credential returned HTTP 200 from
  `GET https://api.e2b.dev/sandboxes` using `X-API-Key`, and template creation
  succeeded. The earlier billing refusal was no longer the blocker.
- Normal sandbox creation failed at guest-daemon authentication.
- `spaces add e2b:e2b-desktop --name e2b-desktop` failed with an invalid-port
  error: the current Space ID parser does not accept contrib-provider IDs.
- After manual recovery of guest access, strict doctor exited 1 with
  **107 passed, 17 failed, 15 skipped**. Failures included image/init and
  inactive systemd-unit checks, audio and variant metadata; required
  interactive checks were skipped.
- A temporary direct HTTPS attachment appeared in the actual native app with
  a running status and live preview. The full viewer reported
  `Could not reach the desktop stream.` Live input was not tested.
- Diagnostic sandbox `i5cymh03dghahjyhdkdp3` was deleted and its absence verified
  against E2B. Temporary registration and guest credentials were removed.
- No hard-coded old key was found in the setup blueprint. The running daemon
  was restarted with the refreshed org secret.

These results do not certify the normal create/register/doctor/viewer flow.
Guest authentication, contrib Space registration, image init/audio and the
full desktop stream remain follow-up work. No live sandbox is retained by this
example, and no paid-machine test runs during an ordinary build or unit suite.

## Static web example

The complete fixture-backed browser app was published to
<https://zen-meadow-kd9n.here.now/>. Anonymous hosting expires on October 25,
2026 at 15:17 UTC unless claimed. Its ownership link is private and is not
part of the repository or public site.

The deployment includes the main app, notch switcher and onboarding under a
visible demo label. It uses the same production React/Wasm build as the
browser preview, not an E2B-connected daemon. The durable reproduction command
is `pnpm build:web` from `apps/cua-spaces`; publish only its `web-dist/` output.

Initial evidence on source commit
`90274d4566397c19733c46104f6b2434848a2224`:

- Production build and TypeScript check passed; all 483 frontend tests passed.
- All 17 published files returned HTTP 200. Binary and script/style assets
  matched their local SHA-256 hashes; HTML matched apart from here.now's
  injected social metadata.
- Main, notch and onboarding entry URLs returned the correct app document.
- WebAssembly compiled successfully, exported the app-core call and was served
  as `application/wasm`. Its memory is non-shared, so thread isolation is not
  required.
- The staged public files were scanned against configured credential values
  before publication. Credentials and ownership state stayed outside them.

These are build, unit-test and HTTP/asset checks, not browser E2E evidence for
the published site. They do not resolve or conceal the native E2B gaps above.
