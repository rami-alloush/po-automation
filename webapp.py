import os
import streamlit as st
import pandas as pd
import ado_api
import spark_api
import json
import time
import urllib.parse
from streamlit_quill import st_quill
import streamlit.components.v1 as components

st.set_page_config(page_title="ADO Automation", layout="wide")

st.title("ADO Automation Assistant")
st.markdown("Automate your Azure DevOps workflows with AI.")


def reset_session_state(prefix):
    keys_to_del = [
        k
        for k in st.session_state.keys()
        if k.startswith(prefix) and "_prompt" not in k
    ]
    for k in keys_to_del:
        del st.session_state[k]
    st.rerun()


@st.dialog("Edit System Prompt")
def prompt_editor(session_key, default_val):
    st.markdown("Edit the system prompt used for this task.")

    # Initialize if not present
    if session_key not in st.session_state:
        st.session_state[session_key] = default_val

    new_val = st.text_area(
        "System Prompt", value=st.session_state[session_key], height=400
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Save", key=f"save_{session_key}"):
            st.session_state[session_key] = new_val
            st.rerun()
    with col2:
        if st.button("Reset to Default", key=f"reset_{session_key}"):
            st.session_state[session_key] = default_val
            st.rerun()


# Navigation
TABS = [
    "User Story Suggestion",
    "Task Generator",
    "Planning Revision",
    "Feature Details",
    "Story Sorter",
    "Bulk Create",
    "Story Replicator",
]

tabs = st.tabs(TABS)

# JS for URL Sync
js = """
<script>
    function syncTabs() {
        const tabs = window.parent.document.querySelectorAll('button[data-baseweb="tab"]');
        const params = new URLSearchParams(window.parent.location.search);
        const activeTab = params.get('tab');

        if (activeTab) {
            for (let i = 0; i < tabs.length; i++) {
                if (tabs[i].innerText === activeTab) {
                    tabs[i].click();
                    break;
                }
            }
        }

        tabs.forEach(tab => {
            tab.addEventListener('click', function() {
                const newUrl = new URL(window.parent.location);
                newUrl.searchParams.set('tab', tab.innerText);
                window.parent.history.pushState({}, '', newUrl);
            });
        });
    }
    setTimeout(syncTabs, 300);
</script>
"""
components.html(js, height=0)


# --- Tab 1: Task Generator ---
with tabs[1]:
    col_h, col_reset, col_btn = st.columns([0.85, 0.1, 0.05])
    with col_h:
        st.header("Task Generator")
    with col_reset:
        if st.button("Clear 🗑️", key="t1_reset", help="Reset Tab"):
            reset_session_state("t1_")
    with col_btn:
        if st.button("⚙️", key="t1_cfg", help="Edit Prompt"):
            prompt_editor("t1_gen_prompt", spark_api.DEFAULT_TASK_GEN_PROMPT)
    st.markdown(
        "Generate tasks from User Stories using Spark API and upload them to Azure DevOps."
    )

    # Session State for Tab 1
    if "t1_user_stories" not in st.session_state:
        st.session_state.t1_user_stories = []
    if "t1_generated_tasks_map" not in st.session_state:
        st.session_state.t1_generated_tasks_map = {}

    # Step 1: Fetch User Story
    st.subheader("1. Fetch User Stories")
    col1, col2 = st.columns([3, 1], vertical_alignment="bottom")
    with col1:
        t1_user_story_ids = st.text_input(
            "Enter User Story IDs (comma or space separated) or Query URL",
            key="t1_input",
        )
    with col2:
        t1_fetch_btn = st.button("Fetch Stories", key="t1_fetch")

    if t1_fetch_btn and t1_user_story_ids:
        try:
            with st.spinner("Fetching User Stories..."):
                input_val = t1_user_story_ids.strip()
                ids = []

                # Logic to determine if input is a URL, Query ID, or list of Story IDs
                if input_val.lower().startswith("http"):
                    # Process as ADO Query URL
                    parsed = urllib.parse.urlparse(input_val)
                    qs = urllib.parse.parse_qs(parsed.query)

                    query_id = None
                    if "tempQueryId" in qs:
                        query_id = qs["tempQueryId"][0]
                    else:
                        # Try to find GUID in path: .../_queries/query/{GUID}
                        parts = parsed.path.rstrip("/").split("/")
                        if "query" in parts:
                            try:
                                idx = parts.index("query")
                                if idx + 1 < len(parts):
                                    query_id = parts[idx + 1]
                            except ValueError:
                                pass

                    if query_id:
                        st.info(f"Executing Query: {query_id}")
                        try:
                            ids = ado_api.execute_query(query_id)
                            if not ids:
                                st.warning(
                                    "Query executed successfully but returned no results."
                                )
                        except Exception as e:
                            if "tempQueryId" in qs:
                                st.error(
                                    f"Failed to execute temporary query. Please **Save** the query in Azure DevOps to generate a permanent link, then try again.\n\nError details: {e}"
                                )
                            else:
                                raise e  # Re-raise to be caught by outer handler
                    else:
                        st.error("Could not extract Query ID from the provided URL.")

                elif (
                    "-" in input_val
                    and len(input_val) > 30
                    and any(c.isalpha() for c in input_val)
                ):
                    # Assume it is a raw Query GUID
                    st.info(f"Executing Query ID: {input_val}")
                    ids = ado_api.execute_query(input_val)
                else:
                    # Assume comma-separated User Story IDs
                    ids = [
                        x.strip()
                        for x in input_val.replace(",", " ").split()
                        if x.strip()
                    ]

                if ids:
                    stories = ado_api.get_work_items_batch(ids)
                    st.session_state.t1_user_stories = stories
                    st.success(f"Fetched {len(stories)} stories.")
                    # Reset generated tasks when new stories are fetched
                    st.session_state.t1_generated_tasks_map = {}
                else:
                    st.warning("Please enter at least one ID.")
        except ado_api.ADOAuthenticationError as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"Error fetching stories: {e}")

    if st.session_state.t1_user_stories:
        st.markdown("### Fetched Stories")
        for story in st.session_state.t1_user_stories:
            with st.expander(
                f"{story['ID']} ({story['Work Item Type']}): {story['Title']}",
                expanded=False,
            ):
                st.markdown(f"**Description:**")
                st.markdown(story["Description"], unsafe_allow_html=True)
                st.markdown(f"**Acceptance Criteria:**")
                st.markdown(story["Acceptance Criteria"], unsafe_allow_html=True)
                if "Web URL" in story:
                    st.link_button("Open in ADO ↗", story["Web URL"])

        # Step 2: Generate Tasks
        st.subheader("2. Generate Tasks")
        if st.button("Generate Tasks for ALL Stories", key="t1_gen"):
            progress_bar = st.progress(0)
            status_text = st.empty()

            for i, story in enumerate(st.session_state.t1_user_stories):
                status_text.text(f"Generating tasks for {story['ID']}...")
                try:
                    # Use custom prompt if set
                    sys_prompt = st.session_state.get(
                        "t1_gen_prompt", spark_api.DEFAULT_TASK_GEN_PROMPT
                    )
                    tasks_response = spark_api.generate_tasks(
                        story, system_prompt=sys_prompt
                    )
                    if "tasks" in tasks_response:
                        tasks = tasks_response["tasks"]
                        # Auto-assign story owner and set Remaining Work
                        story_assignee = story.get("Assigned To", "")
                        if story_assignee == "Unassigned":
                            story_assignee = ""

                        for t in tasks:
                            if story_assignee:
                                t["Assigned To"] = story_assignee
                            # Set Remaining Work = Original Estimate
                            t["Remaining Work"] = t.get("Original Estimate", 0)

                        st.session_state.t1_generated_tasks_map[story["ID"]] = tasks
                    else:
                        st.error(f"Unexpected response format for story {story['ID']}.")
                except Exception as e:
                    st.error(f"Error generating tasks for {story['ID']}: {e}")
                progress_bar.progress((i + 1) / len(st.session_state.t1_user_stories))

            st.success("Task generation complete!")

    # Step 3: Review and Edit Tasks
    if st.session_state.t1_generated_tasks_map:
        st.subheader("3. Review and Edit Tasks")

        t1_final_tasks_map = {}

        for story in st.session_state.t1_user_stories:
            if story["ID"] in st.session_state.t1_generated_tasks_map:
                st.markdown(f"#### Tasks for {story['ID']}: {story['Title']}")

                tasks = st.session_state.t1_generated_tasks_map[story["ID"]]
                df = pd.DataFrame(tasks)

                required_columns = [
                    "Title",
                    "Description",
                    "Original Estimate",
                    "Remaining Work",
                    "Assigned To",
                    "Activity",
                ]
                for col in required_columns:
                    if col not in df.columns:
                        df[col] = "Development" if col == "Activity" else ""

                df = df[
                    required_columns
                    + [c for c in df.columns if c not in required_columns]
                ]

                # Unique key for each editor
                editor_key = f"t1_editor_{story['ID']}"
                t1_edited_df = st.data_editor(
                    df, num_rows="dynamic", width="stretch", key=editor_key
                )

                t1_final_tasks_map[story["ID"]] = t1_edited_df.to_dict(orient="records")

        # Step 4: Upload to ADO
        st.subheader("4. Upload to ADO")
        t1_dry_run = st.checkbox("Dry Run", value=True, key="t1_dry")

        if st.button("Create Tasks in ADO (All Stories)", key="t1_create"):
            total_tasks = sum(len(tasks) for tasks in t1_final_tasks_map.values())
            progress_bar = st.progress(0)
            status_text = st.empty()
            success_count = 0
            errors = []
            processed_count = 0

            for story in st.session_state.t1_user_stories:
                story_id = story["ID"]
                if story_id in t1_final_tasks_map:
                    tasks_to_create = t1_final_tasks_map[story_id]

                    for task in tasks_to_create:
                        processed_count += 1
                        status_text.text(
                            f"Processing: {task['Title']} (Story {story_id})"
                        )
                        try:
                            if not t1_dry_run:
                                ado_api.create_task(story, task)
                            else:
                                time.sleep(0.2)
                            success_count += 1
                        except ado_api.ADOAuthenticationError as e:
                            st.error(f"Authentication Error: {e}")
                            break  # Stop processing if token is invalid
                        except Exception as e:
                            errors.append(
                                f"Failed '{task['Title']}' (Story {story_id}): {e}"
                            )

                        if total_tasks > 0:
                            progress_bar.progress(processed_count / total_tasks)

            if errors:
                st.error(f"Completed with {len(errors)} errors.")
                for err in errors:
                    st.write(err)
            else:
                msg = (
                    f"Dry run: {success_count} tasks would be created."
                    if t1_dry_run
                    else f"Created {success_count} tasks!"
                )
                st.success(msg)

# --- Tab 2: User Story Suggestion ---
# --- Tab 2: User Story Suggestion ---
with tabs[0]:
    col_h, col_reset, col_btn = st.columns([0.85, 0.1, 0.05])
    with col_h:
        st.header("User Story Suggestion")
    with col_reset:
        if st.button("Clear 🗑️", key="t2_reset", help="Reset Tab"):
            reset_session_state("t2_")
    with col_btn:
        if st.button("⚙️", key="t2_cfg", help="Edit Prompt"):
            prompt_editor("t2_suggest_prompt", spark_api.DEFAULT_STORY_SUGGEST_PROMPT)
    st.markdown("Analyze a Feature and suggest missing User Stories.")

    # Session State for Tab 2
    if "t2_feature" not in st.session_state:
        st.session_state.t2_feature = None
    if "t2_existing_stories" not in st.session_state:
        st.session_state.t2_existing_stories = []
    if "t2_suggested_stories" not in st.session_state:
        st.session_state.t2_suggested_stories = None

    # Step 1: Fetch Feature
    st.subheader("1. Fetch Feature")
    col1, col2 = st.columns([3, 1], vertical_alignment="bottom")
    with col1:
        t2_feature_id = st.text_input("Enter Feature ID", key="t2_input")
    with col2:
        t2_fetch_btn = st.button("Fetch Feature", key="t2_fetch")

    if t2_fetch_btn and t2_feature_id:
        try:
            with st.spinner("Fetching Feature and Children..."):
                feature = ado_api.get_work_item(t2_feature_id)
                st.session_state.t2_feature = feature

                # Get children
                child_ids = []
                if "Relations" in feature:
                    for rel in feature["Relations"]:
                        if rel["rel"] == "System.LinkTypes.Hierarchy-Forward":
                            # Extract ID from URL
                            child_id = rel["url"].split("/")[-1]
                            child_ids.append(child_id)

                if child_ids:
                    children = ado_api.get_work_items_batch(child_ids)
                    # Filter for User Stories only? Or keep all children?
                    # Usually Features have User Stories.
                    st.session_state.t2_existing_stories = [
                        c
                        for c in children
                        if c["Work Item Type"] == "User Story"
                        and c["State"] != "Removed"
                    ]
                else:
                    st.session_state.t2_existing_stories = []

                st.success(
                    f"Fetched: {feature['Title']} with {len(st.session_state.t2_existing_stories)} stories."
                )
                st.session_state.t2_suggested_stories = None

        except ado_api.ADOAuthenticationError as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"Error fetching feature: {e}")

    if st.session_state.t2_feature:
        feature = st.session_state.t2_feature

        st.markdown(f"**Feature: {feature['Title']}**")
        with st.expander("Feature Details", expanded=False):
            st.markdown(feature["Description"], unsafe_allow_html=True)

        st.markdown("**Existing User Stories:**")
        if st.session_state.t2_existing_stories:
            for s in st.session_state.t2_existing_stories:
                st.text(f"- {s['ID']}: {s['Title']} ({s['State']})")
        else:
            st.info("No existing user stories found.")

        # Step 2: Suggest Stories
        st.subheader("2. Suggest Stories")
        if st.button("Suggest Stories with Spark", key="t2_suggest"):
            try:
                with st.spinner("Analyzing and Suggesting..."):
                    sys_prompt = st.session_state.get(
                        "t2_suggest_prompt", spark_api.DEFAULT_STORY_SUGGEST_PROMPT
                    )
                    suggestion_response = spark_api.suggest_stories(
                        feature,
                        st.session_state.t2_existing_stories,
                        system_prompt=sys_prompt,
                    )
                    if "stories" in suggestion_response:
                        st.session_state.t2_suggested_stories = suggestion_response[
                            "stories"
                        ]
                    else:
                        st.error("Unexpected response format.")
                        st.json(suggestion_response)
            except Exception as e:
                st.error(f"Error suggesting stories: {e}")

    # Step 3: Review and Edit
    if st.session_state.t2_suggested_stories:
        st.subheader("3. Review and Edit Suggestions")

        df_stories = pd.DataFrame(st.session_state.t2_suggested_stories)
        req_cols_stories = [
            "Title",
            "Description",
            "Acceptance Criteria",
            "Story Points",
            "Assigned To",
            "CMDB App Name",
        ]
        for col in req_cols_stories:
            if col not in df_stories.columns:
                if col == "CMDB App Name":
                    val = (
                        st.session_state.t2_feature.get("CMDB App Name", "")
                        if st.session_state.t2_feature
                        else ""
                    )
                    if not val:
                        val = "CI UDM - UNIFIED DATA MODEL NA"
                    df_stories[col] = val
                else:
                    df_stories[col] = ""

        df_stories = df_stories[
            req_cols_stories
            + [c for c in df_stories.columns if c not in req_cols_stories]
        ]
        t2_edited_df = st.data_editor(
            df_stories, num_rows="dynamic", width="stretch", key="t2_editor"
        )

        # Step 4: Upload
        st.subheader("4. Upload to ADO")
        t2_dry_run = st.checkbox("Dry Run", value=True, key="t2_dry")

        if st.button("Create Stories in ADO", key="t2_create"):
            stories_to_create = t2_edited_df.to_dict(orient="records")
            progress_bar = st.progress(0)
            status_text = st.empty()
            success_count = 0
            errors = []

            for i, story_data in enumerate(stories_to_create):
                status_text.text(f"Processing: {story_data['Title']}")
                try:
                    if not t2_dry_run:
                        ado_api.create_child_work_item(
                            st.session_state.t2_feature, story_data, "User Story"
                        )
                    else:
                        time.sleep(0.5)
                    success_count += 1
                except ado_api.ADOAuthenticationError as e:
                    st.error(f"Authentication Error: {e}")
                    break
                except Exception as e:
                    errors.append(f"Failed '{story_data['Title']}': {e}")
                progress_bar.progress((i + 1) / len(stories_to_create))

            if errors:
                st.error(f"Completed with {len(errors)} errors.")
                for err in errors:
                    st.write(err)
            else:
                msg = (
                    f"Dry run: {success_count} stories would be created."
                    if t2_dry_run
                    else f"Created {success_count} stories!"
                )
                st.success(msg)

# --- Tab 3: Plan Review ---
with tabs[2]:
    col_h, col_reset, col_btn = st.columns([0.85, 0.1, 0.05])
    with col_h:
        st.header("Plan Review")
    with col_reset:
        if st.button("Clear 🗑️", key="t3_reset", help="Reset Tab"):
            reset_session_state("t3_")
    with col_btn:
        if st.button("⚙️", key="t3_cfg", help="Edit Prompt"):
            prompt_editor("t3_review_prompt", spark_api.DEFAULT_PLAN_REVIEW_PROMPT)
    st.markdown("Review an existing Feature's plan (User Stories, Iterations, etc.)")

    # Session State for Tab 3
    if "t3_feature" not in st.session_state:
        st.session_state.t3_feature = None
    if "t3_stories" not in st.session_state:
        st.session_state.t3_stories = []
    if "t3_review_result" not in st.session_state:
        st.session_state.t3_review_result = None

    # Step 1: Fetch Feature
    st.subheader("1. Fetch Feature Plan")
    col1, col2 = st.columns([3, 1], vertical_alignment="bottom")
    with col1:
        t3_feature_id = st.text_input("Enter Feature ID", key="t3_input")
    with col2:
        t3_fetch_btn = st.button("Fetch Plan", key="t3_fetch")

    if t3_fetch_btn and t3_feature_id:
        try:
            with st.spinner("Fetching Feature and Stories..."):
                feature = ado_api.get_work_item(t3_feature_id)
                st.session_state.t3_feature = feature

                # Get children
                child_ids = []
                if "Relations" in feature:
                    for rel in feature["Relations"]:
                        if rel["rel"] == "System.LinkTypes.Hierarchy-Forward":
                            child_id = rel["url"].split("/")[-1]
                            child_ids.append(child_id)

                if child_ids:
                    children = ado_api.get_work_items_batch(child_ids)
                    st.session_state.t3_stories = [
                        c
                        for c in children
                        if c["Work Item Type"] == "User Story"
                        and c["State"] != "Removed"
                    ]
                else:
                    st.session_state.t3_stories = []

                st.success(
                    f"Fetched: {feature['Title']} with {len(st.session_state.t3_stories)} stories."
                )
                st.session_state.t3_review_result = None

        except ado_api.ADOAuthenticationError as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"Error fetching feature: {e}")

    if st.session_state.t3_feature:
        feature = st.session_state.t3_feature
        st.markdown(f"**Feature: {feature['Title']}**")

        if st.session_state.t3_stories:
            st.markdown("**Current Plan (Ordered by Iteration):**")
            # Sort by Iteration Path
            sorted_stories = sorted(
                st.session_state.t3_stories,
                key=lambda x: x.get("Iteration Path", "").replace(
                    "IP Iteration", "~IP Iteration"
                ),
            )

            df_plan = pd.DataFrame(sorted_stories)
            # Handle missing columns if any
            cols_to_show = ["ID", "Title", "State", "Iteration Path"]
            for c in cols_to_show:
                if c not in df_plan.columns:
                    df_plan[c] = ""

            st.dataframe(df_plan[cols_to_show], width="stretch")
        else:
            st.info("No user stories found for this feature.")
            # Debug info
            if "t3_stories" in st.session_state and not st.session_state.t3_stories:
                st.write("Debug Info:")
                if "Relations" in feature:
                    st.write(f"Total Relations: {len(feature['Relations'])}")
                    child_rels = [
                        r
                        for r in feature["Relations"]
                        if r["rel"] == "System.LinkTypes.Hierarchy-Forward"
                    ]
                    st.write(f"Child Relations: {len(child_rels)}")
                    if child_rels:
                        child_ids = [r["url"].split("/")[-1] for r in child_rels]
                        st.write(f"Child IDs: {child_ids}")
                        try:
                            children = ado_api.get_work_items_batch(child_ids)
                            types = [c["Work Item Type"] for c in children]
                            st.write(f"Child Types: {types}")
                        except Exception as e:
                            st.write(f"Error fetching children details: {e}")
                else:
                    st.write("No Relations found in feature object.")

        # Step 2: Review Plan
        st.subheader("2. Review Plan with Spark")
        if st.button("Review Plan", key="t3_review"):
            try:
                with st.spinner("Reviewing Plan..."):
                    sys_prompt = st.session_state.get(
                        "t3_review_prompt", spark_api.DEFAULT_PLAN_REVIEW_PROMPT
                    )
                    review_result = spark_api.review_plan(
                        feature, st.session_state.t3_stories, system_prompt=sys_prompt
                    )
                    st.session_state.t3_review_result = review_result
            except Exception as e:
                st.error(f"Error reviewing plan: {e}")

    # Step 3: Display Results
    if st.session_state.t3_review_result:
        result = st.session_state.t3_review_result
        st.subheader("3. Review Results")

        st.markdown("### Suggestions")
        if "suggestions" in result and result["suggestions"]:
            for sug in result["suggestions"]:
                st.info(sug)
        else:
            st.write("No specific suggestions.")

        st.markdown("### External Dependencies")
        if "external_dependencies" in result and result["external_dependencies"]:
            for dep in result["external_dependencies"]:
                st.warning(dep)
        else:
            st.write("No external dependencies identified.")

        st.markdown("### Missing Steps")
        if "missing_steps" in result and result["missing_steps"]:
            df_missing = pd.DataFrame(result["missing_steps"])
            st.table(df_missing)
        else:
            st.write("No missing steps identified.")

        st.markdown("### Iteration Path Analysis")
        if "iteration_path_analysis" in result and result["iteration_path_analysis"]:
            ordered_display = []
            for path, details in result["iteration_path_analysis"].items():
                ordered_display.append(
                    {
                        "Iteration Path": path,
                        "Story Count": details.get("story_count", 0),
                        "Total Story Points": details.get("total_story_points", 0),
                        "Status": details.get("status", "N/A"),
                    }
                )
            st.table(pd.DataFrame(ordered_display))

# --- Tab 4: Feature Details ---
with tabs[3]:
    col_h, col_reset, col_btn = st.columns([0.85, 0.1, 0.05])
    with col_h:
        st.header("Feature Details Generator")
    with col_reset:
        if st.button("Clear 🗑️", key="t4_reset", help="Reset Tab"):
            reset_session_state("t4_")
    with col_btn:
        if st.button("⚙️", key="t4_cfg", help="Edit Prompt"):
            prompt_editor("t4_details_prompt", spark_api.DEFAULT_FEATURE_DETAILS_PROMPT)
    st.markdown(
        "Generate Feature details (Description, Dependencies, NFRs, AC) from User Stories."
    )

    # Session State
    if "t4_features" not in st.session_state:
        st.session_state.t4_features = (
            {}
        )  # Map ID -> {feature, stories, generated_details}

    # Step 1: Fetch Features
    st.subheader("1. Fetch Features")
    col1, col2 = st.columns([3, 1], vertical_alignment="bottom")
    with col1:
        t4_feature_ids = st.text_input(
            "Enter Feature IDs (comma or space separated)", key="t4_input"
        )
    with col2:
        t4_fetch_btn = st.button("Fetch Features", key="t4_fetch")

    if t4_fetch_btn and t4_feature_ids:
        try:
            with st.spinner("Fetching Features and Stories..."):
                ids = [
                    x.strip()
                    for x in t4_feature_ids.replace(",", " ").split()
                    if x.strip()
                ]
                if ids:
                    st.session_state.t4_features = {}
                    for f_id in ids:
                        feature = ado_api.get_work_item(f_id)

                        # Get children
                        child_ids = []
                        if "Relations" in feature:
                            for rel in feature["Relations"]:
                                if rel["rel"] == "System.LinkTypes.Hierarchy-Forward":
                                    child_id = rel["url"].split("/")[-1]
                                    child_ids.append(child_id)

                        stories = []
                        if child_ids:
                            children = ado_api.get_work_items_batch(child_ids)
                            stories = [
                                c
                                for c in children
                                if c["Work Item Type"] == "User Story"
                                and c["State"] != "Removed"
                            ]

                        st.session_state.t4_features[f_id] = {
                            "feature": feature,
                            "stories": stories,
                            "generated_details": None,
                        }
                    st.success(f"Fetched {len(st.session_state.t4_features)} features.")
        except ado_api.ADOAuthenticationError as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"Error fetching features: {e}")

    # Step 2: Generate Details
    if st.session_state.t4_features:
        st.subheader("2. Generate Details")
        if st.button("Generate Details for ALL Features", key="t4_gen"):
            progress_bar = st.progress(0)
            for i, (f_id, data) in enumerate(st.session_state.t4_features.items()):
                try:
                    sys_prompt = st.session_state.get(
                        "t4_details_prompt", spark_api.DEFAULT_FEATURE_DETAILS_PROMPT
                    )
                    details = spark_api.generate_feature_details(
                        data["feature"], data["stories"], system_prompt=sys_prompt
                    )
                    st.session_state.t4_features[f_id]["generated_details"] = details

                    # Update session state for text areas immediately
                    st.session_state[f"t4_desc_{f_id}"] = details.get("description", "")
                    st.session_state[f"t4_dep_{f_id}"] = details.get(
                        "external_dependencies", ""
                    )
                    st.session_state[f"t4_nfr_{f_id}"] = details.get(
                        "non_functional_requirements", ""
                    )
                    st.session_state[f"t4_ac_{f_id}"] = details.get(
                        "acceptance_criteria", ""
                    )

                except Exception as e:
                    st.error(f"Error generating details for {f_id}: {e}")
                progress_bar.progress((i + 1) / len(st.session_state.t4_features))
            st.success("Generation complete!")
            time.sleep(1)
            st.rerun()

        # Step 3: Review and Edit
        st.subheader("3. Review and Edit")

        t4_updates_map = {}  # Map ID -> {field: value}

        for f_id, data in st.session_state.t4_features.items():
            feature = data["feature"]

            # Initialize session state if not present (first load)
            if f"t4_desc_{f_id}" not in st.session_state:
                st.session_state[f"t4_desc_{f_id}"] = feature.get("Description", "")
            if f"t4_dep_{f_id}" not in st.session_state:
                st.session_state[f"t4_dep_{f_id}"] = feature.get(
                    "External Dependencies", ""
                )
            if f"t4_nfr_{f_id}" not in st.session_state:
                st.session_state[f"t4_nfr_{f_id}"] = feature.get(
                    "Non Functional Requirements", ""
                )
            if f"t4_ac_{f_id}" not in st.session_state:
                st.session_state[f"t4_ac_{f_id}"] = feature.get(
                    "Acceptance Criteria", ""
                )

            with st.expander(f"{feature['ID']}: {feature['Title']}", expanded=True):

                # Description
                st.markdown("**Description**")
                st.session_state[f"t4_desc_{f_id}"] = st_quill(
                    value=st.session_state[f"t4_desc_{f_id}"],
                    html=True,
                    key=f"t4_desc_quill_{f_id}",
                )

                col1, col2 = st.columns(2)
                with col1:
                    # External Dependencies
                    st.markdown("**External Dependencies**")
                    st.session_state[f"t4_dep_{f_id}"] = st_quill(
                        value=st.session_state[f"t4_dep_{f_id}"],
                        html=True,
                        key=f"t4_dep_quill_{f_id}",
                    )

                with col2:
                    # Non Functional Requirements
                    st.markdown("**Non Functional Requirements**")
                    st.session_state[f"t4_nfr_{f_id}"] = st_quill(
                        value=st.session_state[f"t4_nfr_{f_id}"],
                        html=True,
                        key=f"t4_nfr_quill_{f_id}",
                    )

                # Acceptance Criteria
                st.markdown("**Acceptance Criteria**")
                st.session_state[f"t4_ac_{f_id}"] = st_quill(
                    value=st.session_state[f"t4_ac_{f_id}"],
                    html=True,
                    key=f"t4_ac_quill_{f_id}",
                )

                t4_updates_map[f_id] = {
                    "System.Description": st.session_state[f"t4_desc_{f_id}"],
                    "Custom.ExternalDependencies": st.session_state[f"t4_dep_{f_id}"],
                    "Custom.NonFunctionalRequirements_MI": st.session_state[
                        f"t4_nfr_{f_id}"
                    ],
                    "Microsoft.VSTS.Common.AcceptanceCriteria": st.session_state[
                        f"t4_ac_{f_id}"
                    ],
                }

        # Step 4: Upload
        st.subheader("4. Upload to ADO")
        t4_dry_run = st.checkbox("Dry Run", value=True, key="t4_dry")

        if st.button("Update Features in ADO", key="t4_update"):
            progress_bar = st.progress(0)
            success_count = 0
            errors = []

            for i, (f_id, updates) in enumerate(t4_updates_map.items()):
                try:
                    if not t4_dry_run:
                        ado_api.update_work_item(f_id, updates)
                    else:
                        time.sleep(0.5)
                    success_count += 1
                except ado_api.ADOAuthenticationError as e:
                    st.error(f"Authentication Error: {e}")
                    break
                except Exception as e:
                    errors.append(f"Failed {f_id}: {e}")
                progress_bar.progress((i + 1) / len(t4_updates_map))

            if errors:
                st.error(f"Completed with {len(errors)} errors.")
                for err in errors:
                    st.write(err)
            else:
                msg = (
                    f"Dry run: {success_count} features would be updated."
                    if t4_dry_run
                    else f"Updated {success_count} features!"
                )
                st.success(msg)

# --- Tab 5: Story Sorter ---
# --- Tab 5: Story Sorter ---
with tabs[4]:
    col_h, col_reset = st.columns([0.9, 0.1])
    with col_h:
        st.header("Item Sorter (Stories & Bugs)")
    with col_reset:
        if st.button("Clear 🗑️", key="t5_reset", help="Reset Tab"):
            reset_session_state("t5_")
    st.markdown("Fetch User Stories and Bugs for a Feature and view them sorted.")

    if "t5_feature" not in st.session_state:
        st.session_state.t5_feature = None
    if "t5_stories" not in st.session_state:
        st.session_state.t5_stories = []

    # Step 1: Fetch
    st.subheader("1. Fetch Feature")
    col1, col2 = st.columns([3, 1], vertical_alignment="bottom")
    with col1:
        t5_feature_id = st.text_input("Enter Feature ID", key="t5_input")
    with col2:
        t5_fetch_btn = st.button("Fetch Stories", key="t5_fetch")

    if t5_fetch_btn and t5_feature_id:
        try:
            with st.spinner("Fetching Feature and Stories..."):
                feature = ado_api.get_work_item(t5_feature_id)
                st.session_state.t5_feature = feature

                child_ids = []
                if "Relations" in feature:
                    for rel in feature["Relations"]:
                        if rel["rel"] == "System.LinkTypes.Hierarchy-Forward":
                            child_id = rel["url"].split("/")[-1]
                            child_ids.append(child_id)

                if child_ids:
                    children = ado_api.get_work_items_batch(child_ids)
                    st.session_state.t5_stories = [
                        c
                        for c in children
                        if c["Work Item Type"] in ["User Story", "Bug"]
                        and c["State"] != "Removed"
                    ]
                else:
                    st.session_state.t5_stories = []

                st.session_state.t5_msg = f"Fetched: {feature['Title']} with {len(st.session_state.t5_stories)} items."

        except ado_api.ADOAuthenticationError as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"Error fetching feature: {e}")

    # Persistent Display
    if st.session_state.t5_feature:
        st.markdown(f"**Feature: {st.session_state.t5_feature['Title']}**")
        if "t5_msg" in st.session_state:
            st.success(st.session_state.t5_msg)
            del st.session_state["t5_msg"]
        if "t5_success" in st.session_state:
            st.success(st.session_state.t5_success)
            del st.session_state["t5_success"]

    # Step 2: Display and Sort
    if st.session_state.t5_stories:
        st.subheader("2. Items List")

        sort_criteria = st.radio(
            "Sort by:",
            ["Default", "Title (A-Z)", "Iteration Path"],
            horizontal=True,
            key="t5_sort",
        )

        display_stories = st.session_state.t5_stories
        if sort_criteria == "Title (A-Z)":
            display_stories = sorted(
                st.session_state.t5_stories, key=lambda x: x["Title"]
            )
        elif sort_criteria == "Iteration Path":
            display_stories = sorted(
                st.session_state.t5_stories,
                key=lambda x: (
                    x.get("Iteration Path", "").replace(
                        "IP Iteration", "~IP Iteration"
                    ),
                    x["Title"],
                ),
            )

        df = pd.DataFrame(display_stories)
        cols_to_show = [
            "ID",
            "Work Item Type",
            "Title",
            "State",
            "Story Points",
            "Stack Rank",
            "Iteration Path",
        ]
        for c in cols_to_show:
            if c not in df.columns:
                df[c] = ""

        st.dataframe(df[cols_to_show], width="stretch")

        # Reorder in ADO
        if sort_criteria != "Default":
            st.subheader("3. Update ADO Order")
            st.markdown(
                f"This will update the Backlog Priority/Stack Rank of the stories in ADO to match the **{sort_criteria}** order shown above."
            )
            if st.button("Save Sorted Order to ADO", key="t5_reorder"):
                with st.spinner("Updating Story Orders in ADO..."):
                    try:
                        # 1. Collect current ranks
                        current_ranks = [
                            s.get("Stack Rank", 0) for s in st.session_state.t5_stories
                        ]
                        # 2. Sort ranks to get available slots (low numbers = top)
                        available_ranks = sorted(current_ranks)

                        # 3. Handle duplicates/zeros
                        if not available_ranks:
                            available_ranks = [
                                i + 1 for i in range(len(st.session_state.t5_stories))
                            ]

                        start_rank = available_ranks[0]
                        if start_rank <= 0:
                            start_rank = 1

                        base_rank = available_ranks[0] if available_ranks else 1
                        if base_rank == 0:
                            base_rank = 1

                        final_ranks = [
                            base_rank + i for i in range(len(display_stories))
                        ]

                        updates_count = 0
                        errors = []

                        for i, story in enumerate(display_stories):
                            new_rank = final_ranks[i]
                            rank_field = story.get(
                                "Stack Rank Field", "Microsoft.VSTS.Common.StackRank"
                            )

                            try:
                                ado_api.update_work_item(
                                    story["ID"], {rank_field: new_rank}
                                )
                                updates_count += 1
                                # Update local state too
                                story["Stack Rank"] = new_rank
                            except Exception as e:
                                errors.append(f"Failed to update {story['ID']}: {e}")

                            time.sleep(0.1)  # throttling

                        if errors:
                            st.error(f"Completed with {len(errors)} errors.")
                            for e in errors:
                                st.write(e)
                        else:
                            st.session_state.t5_success = f"Successfully reordered {updates_count} stories in ADO based on {sort_criteria}!"
                            st.rerun()

                    except Exception as e:
                        st.error(f"An unexpected error occurred: {e}")

# --- Tab 6: Bulk Create (Chat) ---
# --- Tab 6: Bulk Create (Chat) ---
with tabs[5]:
    col_h, col_reset = st.columns([0.9, 0.1])
    with col_h:
        st.header("Bulk Create via Chat")
    with col_reset:
        if st.button("Clear 🗑️", key="t6_reset", help="Reset Tab"):
            reset_session_state("t6_")
    st.markdown("Chat to define user stories, then extract and create them in bulk.")

    # Session State
    if "t6_messages" not in st.session_state:
        st.session_state.t6_messages = []
    if "t6_extracted_stories" not in st.session_state:
        st.session_state.t6_extracted_stories = []

    # Chat Interface
    st.subheader("1. Chat")

    # Display chat messages with history collapse
    messages = st.session_state.t6_messages
    if len(messages) > 2:
        with st.expander("Previous Chat History", expanded=False):
            for msg in messages[:-2]:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

        # Display the most recent exchange (User + Assistant usually)
        for msg in messages[-2:]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
    else:
        # Display all if short history
        for msg in messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    # Chat input
    if prompt := st.chat_input("Describe the user stories you want to create..."):
        # Add user message
        st.session_state.t6_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Get response
        with st.chat_message("assistant"):
            # Create a placeholder to show immediate feedback
            message_placeholder = st.empty()
            message_placeholder.markdown("🔄 *Thinking...*")

            try:
                with st.spinner("Generating response..."):
                    response_text = spark_api.chat_completion(
                        st.session_state.t6_messages
                    )

                # Update placeholder with final content
                message_placeholder.markdown(response_text)

                # Save to history
                st.session_state.t6_messages.append(
                    {"role": "assistant", "content": response_text}
                )
            except Exception as e:
                message_placeholder.error(f"Error: {e}")

    # Extract Stories
    col_sub, col_btn = st.columns([0.95, 0.05])
    with col_sub:
        st.subheader("2. Extract & Configuration")
    with col_btn:
        st.write("")  # Spacer logic might be needed or just align bottom
        if st.button("⚙️", key="t6_cfg", help="Edit Extraction Prompt"):
            prompt_editor("t6_extract_prompt", spark_api.DEFAULT_CHAT_EXTRACT_PROMPT)

    if st.button("Extract Stories from Chat", key="t6_extract"):
        if not st.session_state.t6_messages:
            st.warning("No chat history to analyze.")
        else:
            with st.spinner("Analyzing chat history..."):
                try:
                    sys_prompt = st.session_state.get(
                        "t6_extract_prompt", spark_api.DEFAULT_CHAT_EXTRACT_PROMPT
                    )
                    result = spark_api.extract_stories_from_chat(
                        st.session_state.t6_messages, system_prompt=sys_prompt
                    )
                    if "stories" in result:
                        st.session_state.t6_extracted_stories = result["stories"]
                        st.success(f"Extracted {len(result['stories'])} stories.")
                    else:
                        st.warning("No stories found in the response.")
                except Exception as e:
                    st.error(f"Error extracting stories: {e}")

    # Configuration Inputs
    col1, col2 = st.columns(2)
    with col1:
        t6_parent_id = st.text_input("Parent Feature ID (Required)", key="t6_parent_id")
    with col2:
        t6_iteration = st.text_input(
            "Iteration Path (Leave empty to use Parent's)", key="t6_iteration"
        )

    # Review and Create
    if st.session_state.t6_extracted_stories:
        st.subheader("3. Review and Create")

        df_t6 = pd.DataFrame(st.session_state.t6_extracted_stories)

        # Ensure columns exist
        cols = [
            "Title",
            "Description",
            "Acceptance Criteria",
            "Story Points",
            "CMDB App Name",
        ]
        for c in cols:
            if c not in df_t6.columns:
                if c == "CMDB App Name":
                    df_t6[c] = "CI UDM - UNIFIED DATA MODEL NA"
                else:
                    df_t6[c] = ""

        # Reorder columns
        df_t6 = df_t6[cols + [c for c in df_t6.columns if c not in cols]]

        t6_edited_df = st.data_editor(
            df_t6, num_rows="dynamic", width="stretch", key="t6_editor"
        )

        t6_dry_run = st.checkbox("Dry Run", value=True, key="t6_dry")

        if st.button("Create Stories in ADO", key="t6_create"):
            stories_to_create = t6_edited_df.to_dict(orient="records")
            progress_bar = st.progress(0)
            status_text = st.empty()
            success_count = 0
            errors = []

            # Get Parent Details if ID provided
            parent_item = None
            if t6_parent_id:
                try:
                    parent_item = ado_api.get_work_item(t6_parent_id)
                except Exception as e:
                    st.error(f"Invalid Parent Feature ID: {e}")
                    stories_to_create = []  # Skip loop

            if not parent_item and stories_to_create:
                st.error("Parent Feature ID is required to create stories.")
                stories_to_create = []

            total = len(stories_to_create)
            for i, story_data in enumerate(stories_to_create):
                status_text.text(f"Processing: {story_data.get('Title', 'Unknown')}")

                # Configure Parent Object with correct Iteration
                effective_parent = parent_item.copy()
                if t6_iteration.strip():
                    effective_parent["Iteration Path"] = t6_iteration.strip()

                try:
                    if not t6_dry_run:
                        ado_api.create_child_work_item(
                            effective_parent, story_data, "User Story"
                        )
                    else:
                        time.sleep(0.5)
                    success_count += 1
                except Exception as e:
                    errors.append(f"Failed {story_data.get('Title')}: {e}")

                if total > 0:
                    progress_bar.progress((i + 1) / total)

            if errors:
                st.error(f"Completed with {len(errors)} errors.")
                for e in errors:
                    st.write(e)
            else:
                if total > 0:
                    msg = (
                        f"Dry run: {success_count} stories would be created."
                        if t6_dry_run
                        else f"Created {success_count} stories!"
                    )
                    st.success(msg)


# --- Tab 7: Story Replicator ---
# --- Tab 7: Story Replicator ---
with tabs[6]:
    col_h, col_reset = st.columns([0.9, 0.1])
    with col_h:
        st.header("Story Replicator")
    with col_reset:
        if st.button("Clear 🗑️", key="t7_reset", help="Reset Tab"):
            reset_session_state("t7_")
    st.markdown("Duplicate a User Story and its tasks into multiple sprints (Cycle).")

    if "t7_source_story" not in st.session_state:
        st.session_state.t7_source_story = None
    if "t7_source_tasks" not in st.session_state:
        st.session_state.t7_source_tasks = []
    if "t7_parent_feature" not in st.session_state:
        st.session_state.t7_parent_feature = None
    if "t7_sprints" not in st.session_state:
        st.session_state.t7_sprints = []

    # Step 1: Fetch Source Story
    st.subheader("1. Fetch Source User Story")
    col1, col2 = st.columns([3, 1], vertical_alignment="bottom")
    with col1:
        t7_story_id = st.text_input("Enter User Story ID to Duplicate", key="t7_input")
    with col2:
        t7_fetch_btn = st.button("Fetch Story", key="t7_fetch")

    if t7_fetch_btn and t7_story_id:
        try:
            with st.spinner("Fetching Story, Parent, and Tasks..."):
                # Fetch Story
                story = ado_api.get_work_item(t7_story_id.strip())
                if story["Work Item Type"] != "User Story":
                    st.error("The ID provided is not a User Story.")
                else:
                    st.session_state.t7_source_story = story

                    # Fetch Parent (Feature)
                    parent_feature = None
                    child_task_ids = []

                    if "Relations" in story:
                        for rel in story["Relations"]:
                            if rel["rel"] == "System.LinkTypes.Hierarchy-Reverse":
                                # Parent
                                parent_url = rel["url"]
                                parent_id = parent_url.split("/")[-1]
                                try:
                                    parent_feature = ado_api.get_work_item(parent_id)
                                except:
                                    pass  # Could not fetch parent
                            elif rel["rel"] == "System.LinkTypes.Hierarchy-Forward":
                                # Child
                                child_id = rel["url"].split("/")[-1]
                                child_task_ids.append(child_id)

                    st.session_state.t7_parent_feature = parent_feature

                    # Fetch Tasks
                    if child_task_ids:
                        tasks = ado_api.get_work_items_batch(child_task_ids)
                        st.session_state.t7_source_tasks = [
                            t
                            for t in tasks
                            if t["Work Item Type"] == "Task" and t["State"] != "Removed"
                        ]
                    else:
                        st.session_state.t7_source_tasks = []

                    # Auto-detect Cycle from Story Iteration
                    current_iter = story.get("Iteration Path", "")
                    if current_iter:
                        if "Sprint" in current_iter or "Iter" in current_iter:
                            parts = current_iter.split("\\")
                            if len(parts) > 1:
                                inferred_cycle = "\\".join(parts[:-1])
                                st.session_state.t7_cycle = inferred_cycle
                        else:
                            st.session_state.t7_cycle = current_iter

                    msg = f"Fetched Story: {story['Title']}"
                    if parent_feature:
                        msg += f" (Parent: {parent_feature['Title']})"
                    else:
                        msg += " (No Parent Feature found - duplication might lack parent link)"
                    msg += f" with {len(st.session_state.t7_source_tasks)} tasks."
                    st.success(msg)

        except Exception as e:
            st.error(f"Error fetching story: {e}")

    # Step 2: Select Sprints
    if st.session_state.t7_source_story:
        st.subheader("2. Select Target Sprints")

        col_cyc1, col_cyc2 = st.columns([3, 1], vertical_alignment="bottom")
        with col_cyc1:
            t7_cycle_path = st.text_input(
                "Cycle Path", value=r"Platts\Scrum\26.02", key="t7_cycle"
            )
        with col_cyc2:
            t7_fetch_sprints_btn = st.button("Fetch Sprints", key="t7_fetch_sprints")

        if t7_fetch_sprints_btn and t7_cycle_path:
            with st.spinner("Fetching Sprints..."):
                try:
                    sprints = ado_api.get_iterations_by_path(t7_cycle_path)
                    st.session_state.t7_sprints = sprints
                    if not sprints:
                        st.warning("No sprints found for this path.")
                except Exception as e:
                    st.error(f"Error fetching sprints: {e}")

        if st.session_state.t7_sprints:
            st.write("Select sprints to duplicate the story into:")

            # Create a dataframe for selection
            df_sprints = pd.DataFrame(st.session_state.t7_sprints)
            if "Select" not in df_sprints.columns:
                df_sprints["Select"] = True  # Default all selected

            t7_selected_sprints_df = st.data_editor(
                df_sprints[["Select", "Name", "Path"]],
                column_config={
                    "Select": st.column_config.CheckboxColumn(required=True)
                },
                disabled=["Name", "Path"],
                hide_index=True,
                key="t7_sprint_selector",
            )

            # Step 3: Replicate
            st.subheader("3. Replicate")
            t7_dry_run = st.checkbox("Dry Run", value=True, key="t7_dry")

            if st.button("Duplicate Story & Tasks", key="t7_duplicate"):
                selected_rows = t7_selected_sprints_df[
                    t7_selected_sprints_df["Select"] == True
                ]

                if selected_rows.empty:
                    st.warning("Please select at least one sprint.")
                else:
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    success_count = 0
                    errors = []
                    total_ops = len(selected_rows)

                    source_story = st.session_state.t7_source_story
                    source_tasks = st.session_state.t7_source_tasks
                    parent = st.session_state.t7_parent_feature

                    if not parent:
                        st.warning(
                            "Proceeding without a Parent Feature link (none found on source)."
                        )

                    for i, row in enumerate(selected_rows.itertuples()):
                        target_path = row.Path
                        target_name = row.Name
                        status_text.text(f"Duplicating to {target_name}...")

                        try:
                            # 1. Create Story
                            story_data = {
                                "Title": source_story["Title"],
                                "Description": source_story["Description"],
                                "Acceptance Criteria": source_story[
                                    "Acceptance Criteria"
                                ],
                                "Story Points": source_story.get("Story Points", 0),
                                "Assigned To": source_story.get("Assigned To", ""),
                                "Iteration Path": target_path,
                                "Area Path": source_story[
                                    "Area Path"
                                ],  # Keep same area
                                "CMDB App Name": source_story.get("CMDB App Name", ""),
                            }

                            if not t7_dry_run:
                                # We need a parent to use create_child_work_item efficiently
                                # If we have a parent, use it.
                                if parent:
                                    new_story = ado_api.create_child_work_item(
                                        parent, story_data, "User Story"
                                    )
                                else:
                                    raise Exception(
                                        "Cannot duplicate without a Parent Feature to attach to."
                                    )

                                # 2. Create Tasks
                                for task in source_tasks:
                                    task_data = {
                                        "Title": task["Title"],
                                        "Description": task["Description"],
                                        "Original Estimate": task.get(
                                            "Original Estimate", 0
                                        ),
                                        "Remaining Work": task.get(
                                            "Original Estimate", 0
                                        ),
                                        "Assigned To": task.get("Assigned To", ""),
                                        "Activity": task.get("Activity", "Development"),
                                        "Iteration Path": target_path,
                                        "Area Path": source_story["Area Path"],
                                    }
                                    ado_api.create_child_work_item(
                                        new_story, task_data, "Task"
                                    )

                            else:
                                time.sleep(0.5)

                            success_count += 1
                        except Exception as e:
                            errors.append(f"Failed in {target_name}: {e}")

                        progress_bar.progress((i + 1) / total_ops)

                    if errors:
                        st.error(f"Completed with {len(errors)} errors.")
                        for e in errors:
                            st.write(e)
                    else:
                        msg = (
                            f"Dry run: Replicated to {success_count} sprints."
                            if t7_dry_run
                            else f"Successfully replicated to {success_count} sprints!"
                        )
                        st.success(msg)


if __name__ == "__main__":
    # run streamlit command
    # os.system("python -m streamlit run webapp.py")
    pass
