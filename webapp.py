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
    if "t1_user_stories" not in st.session_state:
        st.session_state.t1_user_stories = []
    if "t1_generated_tasks_map" not in st.session_state:
        st.session_state.t1_generated_tasks_map = {}

    # Step 1: Fetch User Story
    st.subheader("1. Fetch User Stories")
    col1, col2 = st.columns([3, 1], vertical_alignment="bottom")
    with col1:
        t1_user_story_ids = st.text_input("Enter User Story IDs (comma separated)", value="9950586", key="t1_input")
    with col2:
        t1_fetch_btn = st.button("Fetch Stories", key="t1_fetch")

    if t1_fetch_btn and t1_user_story_ids:
        try:
            with st.spinner("Fetching User Stories..."):
                # Split and clean IDs
                ids = [x.strip() for x in t1_user_story_ids.split(",") if x.strip()]
                if ids:
                    stories = ado_api.get_work_items_batch(ids)
                    st.session_state.t1_user_stories = stories
                    st.success(f"Fetched {len(stories)} stories.")
                    # Reset generated tasks when new stories are fetched
                    st.session_state.t1_generated_tasks_map = {}
                else:
                    st.warning("Please enter at least one ID.")
        except Exception as e:
            st.error(f"Error fetching stories: {e}")

    if st.session_state.t1_user_stories:
        st.markdown("### Fetched Stories")
        for story in st.session_state.t1_user_stories:
             with st.expander(f"{story['ID']}: {story['Title']}", expanded=False):
                st.markdown(f"**Description:**")
                st.markdown(story['Description'], unsafe_allow_html=True)
                st.markdown(f"**Acceptance Criteria:**")
                st.markdown(story['Acceptance Criteria'], unsafe_allow_html=True)
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
                    tasks_response = spark_api.generate_tasks(story)
                    if "tasks" in tasks_response:
                        st.session_state.t1_generated_tasks_map[story['ID']] = tasks_response["tasks"]
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
            if story['ID'] in st.session_state.t1_generated_tasks_map:
                st.markdown(f"#### Tasks for {story['ID']}: {story['Title']}")
                
                tasks = st.session_state.t1_generated_tasks_map[story['ID']]
                df = pd.DataFrame(tasks)
                
                required_columns = ["Title", "Description", "Original Estimate", "Assigned To", "Activity"]
                for col in required_columns:
                    if col not in df.columns:
                        df[col] = "Development" if col == "Activity" else ""
                        
                df = df[required_columns + [c for c in df.columns if c not in required_columns]]
                
                # Unique key for each editor
                editor_key = f"t1_editor_{story['ID']}"
                edited_df = st.data_editor(df, num_rows="dynamic", width="stretch", key=editor_key)
                
                t1_final_tasks_map[story['ID']] = edited_df.to_dict(orient="records")

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
                story_id = story['ID']
                if story_id in t1_final_tasks_map:
                    tasks_to_create = t1_final_tasks_map[story_id]
                    
                    for task in tasks_to_create:
                        processed_count += 1
                        status_text.text(f"Processing: {task['Title']} (Story {story_id})")
                        try:
                            if not t1_dry_run:
                                ado_api.create_task(story, task)
                            else:
                                time.sleep(0.2)
                            success_count += 1
                        except Exception as e:
                            errors.append(f"Failed '{task['Title']}' (Story {story_id}): {e}")
                        
                        if total_tasks > 0:
                            progress_bar.progress(processed_count / total_tasks)
                
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