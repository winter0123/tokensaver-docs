# TokenSaver Docs — local preview status

Source publication preparation: branded as TokenSaver Docs; source requires Pillow 13 or newer after the dependency audit. Older local preview binaries predate that dependency change and are not public releases.

## Native OpenCode v2 preparation — 2026-11-09

- Added native `tokensaver_docs_prepare`, `tokensaver_docs_setup_model` and `tokensaver_docs_read` registration before the compatibility MCP transform. Preparation no longer depends on finding a background MCP tool; these wrappers call the bundled runtime with structured arguments, without model-written shell commands. MCP remains available for compatibility and other tools.
- PASS: a fresh OpenCode 2.1.3 session on macOS arm64 called native `tokensaver_docs_prepare` twice with a completely empty dedicated cache. Free OpenRouter `nvidia/nemotron-3.5-super-vl:free` analyzed five unique synthetic images (six positions including a duplicate): `ready`, five calls, then `ready`, zero calls. No other tools, source reads, CLI/shell fallback or shared earlier cache were used.
- The new verification script rejects CLI/source-read fallback and damaged logs, records actual tool results and isolates each run. 189 source tests passed with six environment skips. Evidence and reviewed Markdown: `qa/opencode-native-20261109/`.
- Final bundles: `dist/model-choice-pqMv8h/plugins-native-verified/`, archives: `release-native-verified/`. This is verification of the native plugin path, not a claim that the separate MCP cold-start issue in OpenCode has been fixed upstream. Global installations remain unchanged.


## Live image analysis with supplied API key — 2026-11-09

- PASS: the product source CLI, invoked by OpenCode, analyzed five synthetic images with the free OpenRouter `nvidia/nemotron-3.5-super-vl:free` model. Six HTML image positions included one duplicate: five initial image calls and zero on repeat. Refund text/amount, chart values, flow direction, no-text illustration and obscured order number were checked against the original images. Preserved image bytes matched.
- PASS: the packaged executable reused these results twice with zero extra image calls; the saved default model was unchanged. The key was supplied only in process environment and was absent from QA model logs.
- NOT_ESTABLISHED: live vision analysis through the actual OpenCode MCP tool. The host sometimes failed to discover the tool and used source CLI instead. This is separate from earlier successful first-setup/placeholder MCP sessions. A new inference through the packaged binary was not separately repeated.
- Minor quality issues: repeated HTML title/h1 and verbose descriptions. Evidence: `qa/opencode-034-tosyr054/live-vision-report.md` and `actual-vision-output/` (private/ignored).


## OpenCode 2.1.3 live verification — 2026-11-09

- PASS: the actual OpenCode host with a free OpenRouter chat model displayed first-use setup and image-incompatible model choices, then prepared synthetic HTML with literal `[이미지]` and correctly read the refund deadline and exception from Markdown.
- Fixed a live-host mismatch: v2 read uses `path`, while the hook recognized only `filePath`. Both are now supported; the actual host rejected raw embedded HTML reads after the fix. 185 source tests passed with six environment skips; the corrected bundled OpenCode tests (3) also passed.
- A request-only vision model selection reached the converter and left the saved default unchanged. Actual vision inference was BLOCKED by a missing `OPENROUTER_API_KEY`; OpenCode stored authentication is not automatically shared with the converter.
- The free chat model also made unnecessary tool calls and bypassed the read hook using shell. The hook is not a sandbox for shell, grep or other tools; host behavior cannot be guaranteed by skill instructions. Only synthetic files were used.
- Updated local bundles: `dist/model-choice-pqMv8h/plugins-v2-read-fix/` and `release-v2-read-fix/`. Earlier `plugins/` in that folder lacks the live read-argument fix. Local detailed evidence: `qa/opencode-034-tosyr054/report.md` (ignored/private QA).


## 0.3.4 model-choice and placeholder preview

- First-use preparation offers conversion model selection or deferral. `setup-model` inspects a user selection; request-only choices do not save defaults, and saving requires explicit confirmation. Legacy provider settings remain readable.
- Image support and price are separate checks. An image-incompatible selection asks users to change models or keep ordinary document text with `[이미지]` at known image positions, without image links/text/descriptions. Unknown support and lookup failures are reported separately; no local OCR fallback is added.
- CLI `prepare --image-mode analyze|preserve|placeholder`, request-specific `--model-provider`/`--model`, MCP and OpenCode carry the selection flow. Manually consenting to an unverified model does not bypass known incompatibility or OpenRouter's price checks. The conversion model is distinct from the host chat model.
- PASS: 184 source tests with six environment-dependent skips; independently two native standalone tests and three bundled OpenCode loader/selection tests passed on macOS arm64. All three bundle and release-archive checksums, dependency checks and Git whitespace checks passed.
- PASS: the native executable queried public OpenRouter model metadata, selected `liquid/lfm-3-1.7b:free` as an image-incompatible model, returned the model-change question without creating output, then preserved HTML text order with `[이미지]` and zero inference calls after explicit placeholder selection. The check used synthetic input and isolated temporary settings; no API key or inference request was used.
- Final local artifacts: `dist/model-choice-pqMv8h/runtime/`, `plugins/` and `release/`. Verification logs are in that parent folder. These are local previews; prior global installations were not replaced. The 0.3.3 records below refer to the previous build.
- NOT_RUN: this new flow with actual model calls in live Codex, Claude Code and OpenCode sessions; Windows/Intel Mac, remote CI and public publication. Model metadata does not establish account availability, and each host controls its user-question UI.

## 0.3.3 image-content local preview

- Image preparation asks whether to preserve images alone or also include visible text and a visual description. The same analysis is reused for standalone and embedded images. Missing models and failed images are reported; edited Markdown is preserved and excluded from automatic context evidence until the conflict is resolved.
- Image and audio provider choices are separate in image preparation and `convert_documents`. Existing `convert` defaults remain compatible; the `context_documents` provider switch enables both kinds and requires consent for both.
- PASS: 150 source tests, including six environment-dependent skips; independently two native standalone tests and three bundled OpenCode loader/hook tests passed on macOS arm64. All three final bundle checksums, `pip check`, and Git whitespace checks passed.
- PASS: five synthetic image fixtures were inspected with OpenCode and the free OpenRouter `nvidia/nemotron-3.5-super-vl:free` model: text, no-text illustration, chart, flowchart and obscured text. This was a direct model check, not an end-to-end call through the packaged converter; usage totals and general accuracy were not established.
- Final local artifacts: `dist/image-content-NZuGnm/runtime-final/`, `plugins-final/` and `release-final/`. Earlier folders in that directory predate the final scanned-PDF fix. These are local previews, not published releases.
- NOT_RUN: actual image analysis through the packaged provider integration, current preview in live Codex/Claude sessions, fresh OpenCode v1/v2 host sessions with this build, Windows/Intel Mac, remote CI, and public publication. Global installations were not replaced.

## OpenCode v2 local compatibility

- The OpenCode bundle exposes a v2 plugin definition that registers the existing local MCP server and read hook; the v1 implementation remains available through its named export.
- The local installer chooses the v1 or v2 loader from the installed OpenCode major version. Reinstall after changing major versions.
- PASS: OpenCode 2.1.3 on macOS arm64 loaded the plugin and connected its MCP server in a temporary project. OpenRouter `nvidia/nemotron-3.5-lightning:free` invoked `prepare_documents` for five user HTML files; 35 images were left untranscribed, and each document has review warnings. Output: `qa/opencode-v2-output/`.
- PASS: 109 source tests (6 environment-dependent skips), plus 3 bundled OpenCode tests and 3 installer tests. A v2 loader was installed into an isolated temporary configuration.
- Bundle preview: `dist/opencode-v2-preview-20261106/opencode/`.
- NOT_RUN: v2 native read redirection in a real session, actual v1 host after this change, Windows/Intel Mac, image transcription, public release or modification of global OpenCode settings.

## Latest: 0.3.2 local review fixes

- Long-section context prioritizes the matching lines and nearby text within the response budget; omitted material remains marked as truncated.
- Shared cache keys include extraction versions where needed, preserve previous outputs and reuse available media transcripts. Oversized input files no longer stop a folder run.
- HTML preparation flags possible CSS background image omissions and catches invalid or oversized image errors. CSS images are not extracted.
- OpenCode v1 redirects literal embedded-image URIs, including UTF-16 HTML, into a per-source user cache. HTML entities in a URI can evade the read hook; call `tokensaver_docs_prepare` for preparation.
- PASS: 108 source tests, with five environment-dependent skips; separately the final macOS arm64 standalone tests (2) and final bundled OpenCode tests (2) passed. The remaining Windows-only test was not run.
- PASS: final native HTML preparation and repeated reuse with zero provider calls, including the refund rule and exception; all three final plugin bundle checksums verified. `pip check` and `git diff --check` passed.
- Synthetic HTML benchmark: in one local run the original HTML, full Markdown and bounded JSON were estimated at 308, 207 and 379 `cl100k_base` tokens respectively. Paths affect counts; model usage and accuracy were not measured.
- Current artifacts: `dist/0.3.2-review-5viqjK/runtime-final`, `plugins-final`, `release-final`. Other folders there are intermediate builds.
- NOT_RUN: Windows/Intel Mac execution, OpenCode v2, fresh Codex/Claude sessions, live provider transcription, remote CI and public directory submission. No existing global installation was replaced.

## Previous: 0.3.1 tool-first HTML support

- Implemented HTML/HTM conversion in the product engine, including Markdown tables, separately preserved original photos, English asset filenames and explicit optional transcription.
- Added bounded offline `prepare` / MCP `prepare_documents` / OpenCode `tokensaver_docs_prepare`, with tool-first skills. Models no longer need to write converters or read raw HTML to use this workflow.
- HTML structure is cached; local images are checked for changes, saved outputs are preserved and cached image transcripts can upgrade a previously untranscribed document without automatic external calls.
- OpenCode v1 native `read` of embedded-image HTML is redirected to prepared Markdown with a 40-line cap. This hook does not cover shell/other host tools and is not a complete sandbox.
- PASS: current native executable + OpenCode hook/preparation tests; 97 passed, one Windows-only test NOT_RUN (98 total).
- PASS: five user HTML documents processed by the product, with 35 byte-identical images, 21 Markdown tables, 864 normalized text fragments in order, English image filenames and zero transcription calls. Repeated preparation reused all five outputs. Results: `qa/html-product-jBpRjT/` (private/ignored).
- PASS: official OpenCode CLI 1.19.5 with OpenRouter `nvidia/nemotron-3.5-lightning:free` used the plugin preparation tool once on a synthetic HTML fixture. No raw read/write/edit event occurred. The model also used a file-discovery shell command; this is one consumer check, not a guarantee for all models/hosts.
- Current packages: `dist/0.3.1-g1g0Cx/runtime-release`, `plugins-release`, `release`. Earlier folders in that directory are intermediate builds.
- NOT_RUN: Windows/Intel Mac actual execution, OpenCode v2 compatibility, remote CI, official registrations, new real vision transcription, public publication and automatic replacement of existing global installations.

Earlier release-readiness records follow.

## Latest: GitHub Releases readiness

- Distribution: GitHub source plus versioned Releases; no server and no required PyPI/npm publication.
- PDFium is bundled, replacing the external Poppler/pdftoppm dependency. PDFium and its dependency license texts accompany the executable and plugin bundles.
- Installers verify requested/package/runtime version agreement. Failed host registration restores the previous marketplace catalog; first-install failure removes the newly written catalog.
- Native builds are manual. The draft-release workflow builds macOS arm64/x64 and Windows x64, verifies all nine archives and creates a draft prerelease only. It has not been run remotely.
- Release archive verification checks version/platform, per-file hashes, duplicate/unsafe entries and completeness, and creates a combined checksum list.
- PASS: 90 tests; NOT_RUN: one Windows-native installer test (91 total, one skipped) with the rebuilt macOS arm64 executable.
- PASS: no-external-renderer scanned-PDF test, bundled local Word/Excel/PDF extraction, macOS release installer/reinstall with local download substitution, preserved cache sentinel, all three plugin integrity/notice checks, dependency check, shell syntax and YAML parsing.
- PASS: wheel/sdist build and archive inspection: new distribution guide/release helper included; QA, node_modules, environment files, work logs and internal plans excluded; PDFium dependency declared.
- Current local artifacts: `dist/release-ready-W03a1r/{runtime,plugins,release,python}`. Older `dist/0.3.0*` builds predate this change.
- User/maintainer installation and update guide: `docs/distribution.md`.
- NOT_RUN: Windows/Intel Mac actual use, remote CI, public release download, signed/notarized OS install, public GitHub/PyPI/npm posting or official directory submission.

Earlier validation records follow; their artifact paths refer to older builds.

## Implemented

- Common complete-result cache, media-unit cache and cross-output partial resume.
- Reuse after source path/model-setting changes; explicit refresh; original and edited-output preservation.
- Verifiable legacy result import; ambiguous legacy mappings block automatic retranscription.
- Per-source/per-unit process locks with bounded waits and integrity checks.
- One-call context, section/adjacent Word-paragraph evidence, full JSON response budget and explicit truncation/pending state.
- Bundled CPU Whisper build, pinned multilingual model catalog, consent/checksum/resume-aware model setup.
- Bundled OpenCode SDK, verified local native installer, stable Claude/Codex marketplace paths, managed OpenCode loader.
- Windows/macOS release installer source, versioned ZIP/checksum generation, wheel/sdist and CI configuration.
- English README, Korean guide, contribution/changelog and issue/PR templates.

## Validation actually run

- PASS: 74 automated tests including the built standalone executable.
- PASS: Python dependencies and diff whitespace checks; Claude manifest validation.
- PASS: macOS independent Word/Excel/PDF conversion and offline token-budgeted context.
- PASS: isolated Claude/Codex native installer registration and repeated installation; bundled OpenCode loader installation.
- PASS: actual OpenCode free model context call with correct refund deadline and exception. No general answer-accuracy guarantee.
- PASS: audio transcription with the bundled Whisper binary and no system Whisper on PATH; recognition accuracy requires separate review.
- PASS: real tiny-model download/checksum; existing verified small-model reuse.
- PASS: macOS install script with release download replaced by local release files.
- PASS: wheel/sdist file inspection excludes local QA, work logs, local plans, node_modules and environment files.
- Synthetic offline benchmark demonstrates one initial mock transcription and zero repeated calls. Text token comparison is not billed usage or a production savings claim.

## Artifacts

Local runtime, platform plugins, release ZIPs/checksums and Python distributions are under `dist/0.3.0/`.
They are not public releases. Older preview directories are retained.

## Not performed / external prerequisites

- Windows, Intel Mac and Linux actual installation or remote CI execution.
- Windows PowerShell execution and real GitHub-release download/install.
- New Claude/Codex paid-model sessions or paid APIs.
- GitHub/PyPI/npm publication, official directory submission, signing and OSS-program application.
- Cross-machine cache sharing is intentionally absent; the shared cache belongs to one local user.

Source changes are uncommitted. Existing source files, user settings, original documents and older artifacts are preserved.

## Subsequent code review

- Fixed false reuse when a PDF requests different visual pages, and reject old PDF cache entries that cannot prove the selected pages were transcribed.
- Exclude conflicting output files from context evidence and include existing Markdown files when searching a source folder.
- Verify output contents before saving a shared result so a concurrent user edit is not reused as an original transcript.
- Local Whisper now detects the spoken language automatically; existing cached transcripts remain reusable.
- PASS: 79 automated tests with the rebuilt macOS arm64 standalone executable; standalone folder-Markdown context and all three bundle checksum checks.
- PASS: a Korean sample and an English synthetic sample produced transcripts locally; this is not a general accuracy evaluation.
- New local runtime, plugin bundles and release archives: `dist/0.3.0-review-verified-eHXgpd/`. The earlier `dist/0.3.0/` artifacts predate these fixes.
- NOT_RUN in that earlier review: fresh Windows, Intel Mac and Linux verification, remote CI, and live provider integration tests. Its external `pdftoppm` requirement has since been removed by the latest PDFium bundle.
