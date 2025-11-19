import streamlit as st
import pandas as pd
import ado_api
import spark_api
import json
import time

st.set_page_config(page_title="ADO Task Generator", layout="wide")

st.title("ADO Task Generator")
st.markdown("Generate tasks from User Stories using Spark API and upload them to Azure DevOps.")

# Session State Initialization
if "user_story" not in st.session_state:
    st.session_state.user_story = None
if "generated_tasks" not in st.session_state:
    st.session_state.generated_tasks = None

# Step 1: Fetch User Story
st.header("1. Fetch User Story")
col1, col2 = st.columns([3, 1], vertical_alignment="bottom")
with col1:
    user_story_id = st.text_input("Enter User Story ID", value="9950586")
with col2:
    fetch_btn = st.button("Fetch Story")

if fetch_btn and user_story_id:
    try:
        with st.spinner("Fetching User Story..."):
            story = ado_api.get_work_item(user_story_id)
            st.session_state.user_story = story
            st.success(f"Fetched: {story['Title']}")
            # Reset generated tasks if new story fetched
            st.session_state.generated_tasks = None 
    except Exception as e:
        st.error(f"Error fetching story: {e}")

if st.session_state.user_story:
    story = st.session_state.user_story
    
    # Display Title and Link
    col_title, col_link = st.columns([4, 1], vertical_alignment="center")
    with col_title:
        st.subheader(f"{story['Title']}")
    with col_link:
        if "Web URL" in story:
            st.link_button("Open in ADO ↗", story["Web URL"])
            
    with st.expander("User Story Details", expanded=True):
        st.markdown(f"**Description:**")
        st.markdown(story['Description'], unsafe_allow_html=True)
        st.markdown(f"**Acceptance Criteria:**")
        st.markdown(story['Acceptance Criteria'], unsafe_allow_html=True)

    # Step 2: Generate Tasks
    st.header("2. Generate Tasks")
    if st.button("Generate Tasks with Spark"):
        try:
            with st.spinner("Generating tasks... (this may take a moment)"):
                tasks_response = spark_api.generate_tasks(story)
                if "tasks" in tasks_response:
                    st.session_state.generated_tasks = tasks_response["tasks"]
                else:
                    st.error("Unexpected response format from Spark API. Expected 'tasks' key.")
                    st.json(tasks_response)
        except Exception as e:
            st.error(f"Error generating tasks: {e}")

# Step 3: Review and Edit Tasks
if st.session_state.generated_tasks:
    st.header("3. Review and Edit Tasks")
    
    # Convert to DataFrame for editing
    df = pd.DataFrame(st.session_state.generated_tasks)
    
    # Ensure columns exist
    required_columns = ["Title", "Description", "Original Estimate", "Assigned To", "Activity"]
    for col in required_columns:
        if col not in df.columns:
            if col == "Activity":
                df[col] = "Development"
            else:
                df[col] = ""
            
    # Reorder columns
    df = df[required_columns + [c for c in df.columns if c not in required_columns]]

    edited_df = st.data_editor(df, num_rows="dynamic", width="stretch")

    # Step 4: Upload to ADO
    st.header("4. Upload to ADO")
    
    dry_run = st.checkbox("Dry Run (Simulate upload without creating items)", value=True)
    
    if st.button("Create Tasks in ADO"):
        tasks_to_create = edited_df.to_dict(orient="records")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        success_count = 0
        errors = []
        
        for i, task in enumerate(tasks_to_create):
            status_text.text(f"Processing task {i+1}/{len(tasks_to_create)}: {task['Title']}")
            
            try:
                if not dry_run:
                    ado_api.create_task(st.session_state.user_story, task)
                else:
                    # Simulate delay
                    time.sleep(0.5)
                success_count += 1
            except Exception as e:
                errors.append(f"Failed to create '{task['Title']}': {e}")
            
            progress_bar.progress((i + 1) / len(tasks_to_create))
            
        if errors:
            st.error(f"Completed with {len(errors)} errors.")
            for err in errors:
                st.write(err)
        else:
            if dry_run:
                st.success(f"Dry run completed! {success_count} tasks would have been created.")
            else:
                st.success(f"Successfully created {success_count} tasks in ADO!")