import os
import streamlit as st
import pandas as pd
import ado_api
import spark_api
import json
import time

st.set_page_config(page_title="ADO Automation", layout="wide")

st.title("ADO Automation Assistant")
st.markdown("Automate your Azure DevOps workflows with AI.")

# Tabs
tab1, tab2 = st.tabs(["Task Generator", "User Story Suggestion"])

# --- Tab 1: Task Generator ---
with tab1:
    st.header("Task Generator")
    st.markdown("Generate tasks from User Stories using Spark API and upload them to Azure DevOps.")

    # Session State for Tab 1
    if "t1_user_story" not in st.session_state:
        st.session_state.t1_user_story = None
    if "t1_generated_tasks" not in st.session_state:
        st.session_state.t1_generated_tasks = None

    # Step 1: Fetch User Story
    st.subheader("1. Fetch User Story")
    col1, col2 = st.columns([3, 1], vertical_alignment="bottom")
    with col1:
        t1_user_story_id = st.text_input("Enter User Story ID", value="9950586", key="t1_input")
    with col2:
        t1_fetch_btn = st.button("Fetch Story", key="t1_fetch")

    if t1_fetch_btn and t1_user_story_id:
        try:
            with st.spinner("Fetching User Story..."):
                story = ado_api.get_work_item(t1_user_story_id)
                st.session_state.t1_user_story = story
                st.success(f"Fetched: {story['Title']}")
                st.session_state.t1_generated_tasks = None 
        except Exception as e:
            st.error(f"Error fetching story: {e}")

    if st.session_state.t1_user_story:
        story = st.session_state.t1_user_story
        
        col_title, col_link = st.columns([4, 1], vertical_alignment="center")
        with col_title:
            st.markdown(f"**{story['Title']}**")
        with col_link:
            if "Web URL" in story:
                st.link_button("Open in ADO ↗", story["Web URL"])
                
        with st.expander("User Story Details", expanded=False):
            st.markdown(f"**Description:**")
            st.markdown(story['Description'], unsafe_allow_html=True)
            st.markdown(f"**Acceptance Criteria:**")
            st.markdown(story['Acceptance Criteria'], unsafe_allow_html=True)

        # Step 2: Generate Tasks
        st.subheader("2. Generate Tasks")
        if st.button("Generate Tasks with Spark", key="t1_gen"):
            try:
                with st.spinner("Generating tasks..."):
                    tasks_response = spark_api.generate_tasks(story)
                    if "tasks" in tasks_response:
                        st.session_state.t1_generated_tasks = tasks_response["tasks"]
                    else:
                        st.error("Unexpected response format from Spark API.")
                        st.json(tasks_response)
            except Exception as e:
                st.error(f"Error generating tasks: {e}")

    # Step 3: Review and Edit Tasks
    if st.session_state.t1_generated_tasks:
        st.subheader("3. Review and Edit Tasks")
        
        df = pd.DataFrame(st.session_state.t1_generated_tasks)
        required_columns = ["Title", "Description", "Original Estimate", "Assigned To", "Activity"]
        for col in required_columns:
            if col not in df.columns:
                df[col] = "Development" if col == "Activity" else ""
                
        df = df[required_columns + [c for c in df.columns if c not in required_columns]]
        t1_edited_df = st.data_editor(df, num_rows="dynamic", width="stretch", key="t1_editor")

        # Step 4: Upload to ADO
        st.subheader("4. Upload to ADO")
        t1_dry_run = st.checkbox("Dry Run", value=True, key="t1_dry")
        
        if st.button("Create Tasks in ADO", key="t1_create"):
            tasks_to_create = t1_edited_df.to_dict(orient="records")
            progress_bar = st.progress(0)
            status_text = st.empty()
            success_count = 0
            errors = []
            
            for i, task in enumerate(tasks_to_create):
                status_text.text(f"Processing: {task['Title']}")
                try:
                    if not t1_dry_run:
                        ado_api.create_task(st.session_state.t1_user_story, task)
                    else:
                        time.sleep(0.5)
                    success_count += 1
                except Exception as e:
                    errors.append(f"Failed '{task['Title']}': {e}")
                progress_bar.progress((i + 1) / len(tasks_to_create))
                
            if errors:
                st.error(f"Completed with {len(errors)} errors.")
                for err in errors:
                    st.write(err)
            else:
                msg = f"Dry run: {success_count} tasks would be created." if t1_dry_run else f"Created {success_count} tasks!"
                st.success(msg)

# --- Tab 2: User Story Suggestion ---
with tab2:
    st.header("User Story Suggestion")
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
                    st.session_state.t2_existing_stories = [c for c in children if c["Work Item Type"] == "User Story"]
                else:
                    st.session_state.t2_existing_stories = []
                
                st.success(f"Fetched: {feature['Title']} with {len(st.session_state.t2_existing_stories)} stories.")
                st.session_state.t2_suggested_stories = None

        except Exception as e:
            st.error(f"Error fetching feature: {e}")

    if st.session_state.t2_feature:
        feature = st.session_state.t2_feature
        
        st.markdown(f"**Feature: {feature['Title']}**")
        with st.expander("Feature Details", expanded=False):
            st.markdown(feature['Description'], unsafe_allow_html=True)

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
                    suggestion_response = spark_api.suggest_stories(feature, st.session_state.t2_existing_stories)
                    if "stories" in suggestion_response:
                        st.session_state.t2_suggested_stories = suggestion_response["stories"]
                    else:
                        st.error("Unexpected response format.")
                        st.json(suggestion_response)
            except Exception as e:
                st.error(f"Error suggesting stories: {e}")

    # Step 3: Review and Edit
    if st.session_state.t2_suggested_stories:
        st.subheader("3. Review and Edit Suggestions")
        
        df_stories = pd.DataFrame(st.session_state.t2_suggested_stories)
        req_cols_stories = ["Title", "Description", "Acceptance Criteria", "Story Points", "Assigned To"]
        for col in req_cols_stories:
            if col not in df_stories.columns:
                df_stories[col] = ""
        
        df_stories = df_stories[req_cols_stories + [c for c in df_stories.columns if c not in req_cols_stories]]
        t2_edited_df = st.data_editor(df_stories, num_rows="dynamic", width="stretch", key="t2_editor")

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
                        ado_api.create_child_work_item(st.session_state.t2_feature, story_data, "User Story")
                    else:
                        time.sleep(0.5)
                    success_count += 1
                except Exception as e:
                    errors.append(f"Failed '{story_data['Title']}': {e}")
                progress_bar.progress((i + 1) / len(stories_to_create))
                
            if errors:
                st.error(f"Completed with {len(errors)} errors.")
                for err in errors:
                    st.write(err)
            else:
                msg = f"Dry run: {success_count} stories would be created." if t2_dry_run else f"Created {success_count} stories!"
                st.success(msg)

if __name__ == "__main__":
    # run streamlit command
    # os.system("python -m streamlit run webapp.py")
    pass