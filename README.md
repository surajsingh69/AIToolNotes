# TechSansar v2 — AI Tools Tutorials & Comparisons

## What changed from your original script, and why

1. **Niche**: switched from rewriting general news headlines to writing
   tutorials/comparisons about AI tools, grounded in the tool's own release
   notes / blog / docs (real fetched page text, not just a headline).
   General news rewrites compete directly with outlets like BBC/Reuters/CNN
   for the same story and rank far below them — you were structurally
   unable to win there. Tutorials and comparisons are evergreen, have real
   commercial/affiliate potential, and don't require you to "beat" a wire
   service to a story.

2. **Grounded generation**: the script now fetches the actual source page
   text and feeds it to the model, and explicitly asks for original
   analysis/opinion rather than a rewrite. This matters for Google's
   "scaled content abuse" spam policy, which targets pages generated at
   scale with little original value — regardless of whether a human or AI
   made them. Headline-only rewrites are close to a textbook case of this;
   grounded tutorials with real added analysis are much safer, though
   nothing here guarantees rankings — genuine usefulness is what does that.

3. **Lower daily volume**: capped at 2 posts/run instead of 8. Fewer,
   better articles beat more, thinner ones both for spam-policy risk and
   for reader trust.

4. **No hardcoded secrets**: your Groq key was hardcoded in plain text in
   the original file and shared with me in this upload — **revoke and
   regenerate it in your Groq console immediately**, then never hardcode
   a new one. This version reads all secrets from environment variables.

5. **Runs on GitHub Actions**: fixes the "only posts when my device is on"
   problem. The workflow in `.github/workflows/post.yml` runs on GitHub's
   own servers on a daily schedule (06:00 UTC by default — edit the cron
   line to change it), with zero dependency on your laptop being open.

## One-time setup

1. Create a **private** GitHub repo and push this folder to it.
   (Private, so `posted_titles.json` and workflow logs aren't public —
   though secrets themselves are never exposed either way.)

2. On your own machine, run `blog_automation.py` once locally (with
   `GROQ_API_KEY` and `BLOG_ID` set as environment variables) to complete
   the Google OAuth flow and generate a fresh `token.json`. This is the
   only step that needs your device — after this, GitHub runs everything.

3. In the GitHub repo: **Settings → Secrets and variables → Actions**,
   add these repository secrets:
   - `GROQ_API_KEY` — your **new**, rotated Groq key
   - `BLOG_ID` — your Blogger blog ID
   - `GOOGLE_CREDENTIALS_JSON` — full contents of your `credentials.json`
   - `GOOGLE_TOKEN_JSON` — full contents of your fresh `token.json`

4. Do **not** commit `credentials.json` or `token.json` to the repo itself
   — the workflow recreates them at runtime from secrets. Add both to a
   `.gitignore` file.

5. Push. The workflow will run automatically on schedule, or you can
   trigger it manually from the repo's "Actions" tab any time to test it.

## Monetization notes (honest expectations)

- AdSense alone on a new blog rarely reaches $1k quickly — RPMs for tech
  content are decent but volume takes time to build.
- The realistic path to $1k faster is stacking **affiliate links** for the
  AI tools you cover (many have referral/affiliate programs) alongside ads.
- Consider spending 10–15 minutes a week skimming published articles for
  accuracy and adding one line of your own take where useful — this is a
  small time cost that meaningfully improves both trustworthiness and
  compliance with Google's content-quality guidance.
