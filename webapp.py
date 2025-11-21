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
tab2, tab1, tab3 = st.tabs(["User Story Suggestion", "Task Generator", "Planning Revision"])

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
                    st.session_state.t2_existing_stories = [c for c in children if c["Work Item Type"] == "User Story" and c["State"] != "Removed"]
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

# --- Tab 3: Planning Revision ---
with tab3:
    st.header("Planning Revision")
    st.markdown("Review the execution plan of a Feature and its User Stories.")

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
                    st.session_state.t3_stories = [c for c in children if c["Work Item Type"] == "User Story" and c["State"] != "Removed"]
                else:
                    st.session_state.t3_stories = []
                
                st.success(f"Fetched: {feature['Title']} with {len(st.session_state.t3_stories)} stories.")
                st.session_state.t3_review_result = None

        except Exception as e:
            st.error(f"Error fetching feature: {e}")

    if st.session_state.t3_feature:
        feature = st.session_state.t3_feature
        st.markdown(f"**Feature: {feature['Title']}**")
        
        if st.session_state.t3_stories:
            st.markdown("**Current Plan (Ordered by Iteration):**")
            # Sort by Iteration Path
            sorted_stories = sorted(st.session_state.t3_stories, key=lambda x: x.get('Iteration Path', ''))
            
            df_plan = pd.DataFrame(sorted_stories)
            # Handle missing columns if any
            cols_to_show = ["ID", "Title", "State", "Iteration Path"]
            for c in cols_to_show:
                if c not in df_plan.columns:
                    df_plan[c] = ""
            
            st.dataframe(df_plan[cols_to_show], use_container_width=True)
        else:
            st.info("No user stories found for this feature.")
            # Debug info
            if "t3_stories" in st.session_state and not st.session_state.t3_stories:
                st.write("Debug Info:")
                if "Relations" in feature:
                    st.write(f"Total Relations: {len(feature['Relations'])}")
                    child_rels = [r for r in feature["Relations"] if r["rel"] == "System.LinkTypes.Hierarchy-Forward"]
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
                    review_result = spark_api.review_plan(feature, st.session_state.t3_stories)
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

        st.markdown("### Proposed Order")
        if "proposed_order" in result and result["proposed_order"]:
             # Create a lookup for existing stories
             story_map = {str(s["ID"]): s["Title"] for s in st.session_state.t3_stories}
             
             # Determine old order
             sorted_stories = sorted(st.session_state.t3_stories, key=lambda x: x.get('Iteration Path', ''))
             old_order_map = {str(s["ID"]): i + 1 for i, s in enumerate(sorted_stories)}

             ordered_display = []
             for i, story_id in enumerate(result["proposed_order"]):
                 s_id_str = str(story_id)
                 title = story_map.get(s_id_str, "Unknown Story")
                 ordered_display.append({
                     "Old Order": old_order_map.get(s_id_str, "N/A"),
                     "ID": story_id,
                     "Title": title
                 })
             
             st.table(pd.DataFrame(ordered_display))

if __name__ == "__main__":
    # run streamlit command
    # os.system("python -m streamlit run webapp.py")
    pass