# Automation Toolkit for Product Owners

A Streamlit-based application to automate Feature and User Story management in Azure DevOps (ADO) using generative AI (Spark/OpenAI).

## Features

-   **User Story Suggestion**: Analyze a Feature title and description to suggest comprehensive User Stories.
-   **Task Generator**: breakdowns User Stories into actionable Tasks with estimates.
-   **Planning Revision**: Review the execution order and dependencies of User Stories within a Feature.
-   **Feature Details Generator**: Auto-generate Feature Description, Acceptance Criteria, and NFRs based on its child User Stories.

## Prerequisites

-   Python 3.8+
-   An Azure DevOps account and Personal Access Token (PAT).
-   Access to the Spark/OpenAI API.

## Installation

1.  Clone the repository:
    ```bash
    git clone <repository-url>
    cd po-automation
    ```

2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

3.  Configure environment variables:
    -   Copy `.env.example` to `.env`:
        ```bash
        cp .env.example .env
        ```
    -   Open `.env` and fill in your details:
        -   `ADO_PAT_TOKEN`: Your Azure DevOps Personal Access Token.
        -   `ADO_ORGANIZATION`: Your ADO Organization name. (Default: spglobal)
        -   `ADO_PROJECT`: Your ADO Project name. (Default: Platts)
        -   `SPARK_API_KEY`: Your Spark API Key.
        -   `SPARK_ENV_URL`: Spark API URL (Default: https://sparkuatapi.spglobal.com).
        -   `SPARK_APP_ID`: Spark App ID (Default: sparkassist).
        -   `SPARK_MODEL`: Model name (Default: gpt-4o-2024-11-20).

## Usage

Run the Streamlit application:

```bash
streamlit run webapp.py
```

The application will open in your default web browser.

## Security Note

-   **Never commit your `.env` file.** It is included in `.gitignore` by default.
-   Ensure your ADO PAT has the minimum required scopes (Work Item Read/Write).

## License
MIT License
