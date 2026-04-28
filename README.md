# PathEval

PathEval is a blind pathology image review application for evaluating the quality of AI-generated H&E pathology images. It gives pathologists and clinicians a structured workflow for scoring each image, checking whether prompt-required morphology is visible, and exporting the results as CSV.

Live site: https://patheval.vercel.app

## System Requirements

### Software Dependencies

| Requirement | Version / Notes |
| --- | --- |
| Operating system | macOS, Linux, or Windows with Node.js support |
| Node.js | >= 20.9.0 required by Next.js; tested with 24.13.0 |
| npm | Tested with 11.6.2 |
| Next.js | 16.2.4 |
| React | 19.2.5 |
| React DOM | 19.2.5 |
| TypeScript | 5.9.3 |
| Optional R2 migration dependency | `@aws-sdk/client-s3` 3.1038.0 |

### Tested Environment

The current version has been tested on:

| Component | Tested Version |
| --- | --- |
| OS | macOS 13.3, arm64 |
| Node.js | 24.13.0 |
| npm | 11.6.2 |
| Next.js | 16.2.4 |
| Deployment platform | Vercel production deployment |

### Hardware

No non-standard hardware is required. A normal desktop or laptop that can run Node.js and a modern web browser is sufficient.

## Installation Guide

Clone the repository and install dependencies:

```bash
npm install
```

Typical install time on a normal desktop computer is about 1-3 minutes, depending on network speed and npm cache state.

Start the local development server:

```bash
npm run dev
```

Open `http://localhost:3000` in a browser.

To build a production bundle:

```bash
npm run build
```

To run the automated tests:

```bash
npm test
```

## Demo

### Run the Demo

The public repository does not include the full evaluation CSV files. Add your own
`data_filtered.csv` in the project root to load cases locally.

```bash
npm install
npm run dev
```

Then open `http://localhost:3000`.

### Expected Demo Output

Without a local CSV, the browser shows an empty-state message. With a local
`data_filtered.csv`, the browser should show the PathEval welcome screen. After
entering an evaluator name, the application opens the blind review interface with:

- One pathology image displayed at a time.
- Case diagnosis and source prompt.
- Three 1-5 scoring sliders.
- A checklist of expected pathology features.
- Optional comments.
- Progress tracking.
- CSV export.

Exported CSV files contain:

- `doctor_name`
- `image_id`
- `score_histology`
- `score_cytology`
- `score_microenvironment`
- `comment`
- `checked_features`
- `qa_accuracy`
- `qa_correct_count`
- `qa_total_count`
- `timestamp`

Expected runtime for the demo on a normal desktop computer is less than 1 minute to start the local server after installation. Individual review time depends on the evaluator; a single case can usually be scored in under 1 minute once the image is loaded.

## Instructions for Use

1. Open the live site or the local development URL.
2. Enter the evaluator name.
3. Review each case image without using model identity as a cue.
4. Score the image across:
   - Histology structure: low-power architecture and organ/lesion plausibility.
   - Cytology features: cellular detail, nuclear features, and biologic realism.
   - Microenvironment: cell polarity, stromal response, and tissue interaction.
5. Select checklist features only when they are visible in the pathology image.
6. Add optional comments for image-specific issues.
7. Click `Save and next` to store the evaluation in the browser and move forward.
8. Use the left task list to revisit completed or pending cases.
9. Click `Export CSV` when the assigned cases are complete.

Review data is stored in the browser's local storage until it is exported or cleared. It is not submitted to a backend server.

## Running the Software on Your Own Data

Prepare a CSV file named `data_filtered.csv` in the project root. The app expects the following columns:

| Column | Purpose |
| --- | --- |
| `id` | Unique image/case identifier. |
| `prompt_idx` | Source prompt group identifier. |
| `image_path` | URL for the pathology image. The image should be reachable from the browser. |
| `model` | Generation model name. This is loaded from the data but intentionally hidden in the UI. |
| `disease` | Case diagnosis displayed to the reviewer. |
| `prompt` | Source generation prompt shown with the image. |
| `questions` | JSON-style list of expected pathology features used for the checklist. |

Example row:

```csv
id,prompt_idx,image_path,model,disease,prompt,questions
case_001,1,https://example.com/image_001.png,model_a,Example diagnosis,"Generate an H&E pathology image.","[""Feature A"", ""Feature B""]"
```

After adding `data_filtered.csv`, run:

```bash
npm run dev
```

Open `http://localhost:3000` and verify that the new cases appear in the task list.

Full evaluation CSV files are kept outside the public repository.

## Reproduction Instructions

To reproduce the data collection workflow:

1. Start from a clean browser profile or click `Clear local records` in the app.
2. Run the app locally with `npm run dev` or open the production site.
3. Enter the evaluator name.
4. Complete the scoring and checklist for each assigned image.
5. Export the CSV.
6. Use the exported CSV fields to calculate quantitative summaries, such as mean histology score, mean cytology score, mean microenvironment score, and checklist feature-match accuracy.

The app computes per-image `qa_accuracy` as:

```text
qa_accuracy = qa_correct_count / qa_total_count
```

where `qa_correct_count` is the number of selected checklist features and `qa_total_count` is the number of expected features for that image.

## Data and Evaluation Design

PathEval performs a blind review: generation model details are present in the source data but hidden in the reviewer interface. The displayed review information is limited to the pathology image, case diagnosis, source prompt, and the expected feature checklist.

The scoring dimensions are:

- Histology structure: low-power overall architecture and anatomic plausibility.
- Cytology features: high-power cellular detail and biologic realism.
- Microenvironment: cell arrangement, polarity, stromal response, and tissue interaction.

## Useful Scripts

```bash
npm run r2:setup
npm run r2:migrate
```

The R2 scripts are optional helpers for migrating image assets from the original image URLs into a Cloudflare R2 bucket and rewriting the image paths into a new CSV.

## Deployment

The project is linked to Vercel as `patheval`.

Production URL:

https://patheval.vercel.app
