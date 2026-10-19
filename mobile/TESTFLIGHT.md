# Den on iPhone

The `testflight` EAS profile builds a standalone release app for TestFlight.
It calls `https://torontodecorden.com/api/v1` and does not need a local Expo
development server after installation. The app name is Den and its proposed
Apple bundle identifier is `com.torontodecorden.den`. If an existing Apple app
record already uses a different identifier, use that existing identifier instead
before the first build. The Expo project slug remains `mobile`.

You need an Expo account and an active Apple Developer Program membership with
access to App Store Connect. EAS can build iOS apps in the cloud from Windows.
Keep Apple credentials and signing keys out of GitHub and chat.

From the repository's `mobile` directory after pulling the deployment branch:

```powershell
npm ci
npx eas-cli@latest login
npx eas-cli@latest init
npx eas-cli@latest build --platform ios --profile testflight
```

Choose the Expo account that should own the app during project initialization.
EAS adds the real project ID to the app config. No project ID or Apple team ID
has been invented in this repository. Let EAS manage signing credentials if this
is a new app; select the correct Apple developer team when prompted. Commit the
project-linking configuration changes after checking that they contain no secrets.

When the signed build succeeds, upload it:

```powershell
npx eas-cli@latest submit --platform ios --profile testflight --latest
```

Follow the CLI prompts to select/create the matching App Store Connect app
record. If asked for `ascAppId`, use its numeric Apple ID from App Store Connect
App Information. Submission uploads the build to Apple; it does not publish an
App Store release. Wait for Apple's processing, answer any required compliance
questions for this app, and add testers under App Store Connect > Den > TestFlight.
External testers may require Apple's beta review. Install Apple's TestFlight
app on the iPhone and accept the invitation to install Den.

The cloud build and Apple upload have not been run by adding these files. Those
steps require account access. Expo config, type checks and JavaScript bundling
cannot verify native signing or replace testing the installed app on an iPhone.

The deployed database is separate from local SQLite: use a deployed account or
register a new customer account in the app. For a vendor account, register on
the website and use the same credentials in the app. Test login, logout, vendor
discovery, filtering and event matching against the live backend. Photo upload
delivery requires the backend's external media storage to be configured.
