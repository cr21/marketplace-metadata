# UI Specification – Update Existing Catalog

This document describes the UI flow and backend behavior for the Update Existing Catalog feature in the Metadata Catalog Agent.

---

# UI Design Reference

The UI implementation should strictly follow the layout, workflow, and visual behavior shown in the attached reference images:

- X_1.png
- X_2.png
- X_3.png
- X_4.png
- X_5.png

These reference images should be used for:

- Stepper/progress flow design
- Activity side panel behavior
- Registry update workflow screens
- Success and no-change states
- Incremental update result display
- Metadata diff visualization
- Button placement and interaction flow
- Table/result rendering behavior

## Important UI Requirement

The final UI should visually match the attached reference screens as closely as possible.

Particularly:

- X_5 screen should display:
  - "Registry is up to date"
  - Registry table path
  - Number of inserted/updated rows
  - Incremental update results only

- Activity panel should stream all backend actions in real time.

- Only delta changes (new or modified metadata records) should be displayed in the final result screen.

- If no changes are detected, the UI should show a clean success/no-op state exactly similar to the X_5 reference image.

---

# Step 1 : Landing Page

Two Options:

1.1 Build a new catalog  
1.2 Update an existing catalog

Activity side panel will stream all agent actions.

![landing_page](/UI_Specs/1_landing_page.png)

---

# Step 2 : (1.2 Extension on Update Existing Catalog)

When user clicks on Update an existing catalog.

![X_1](/UI_Specs/X_1.png)

## Step 2.1 : Identify Existing Catalog

User provides:

- Project ID
- Dataset Name

Agent assumes the registry table exists in the same project by default.

Advanced section can later be expanded to override registry location.

### UI Behavior

- User enters Project ID
- User enters Dataset Name
- User clicks on Update registry button

### Backend Actions

- Agent validates the project and dataset
- Agent identifies the registry table
- Agent starts comparison workflow
- Activity panel streams live actions

---

![X_2](/UI_Specs/X_2.png)

# Step 3 : Diff and Write

After user clicks on Update registry, the system starts the update workflow.

## Step 3.1 : Reading Existing Registry

The agent performs the following actions:

- Reads existing rows from data_catalog_registry
- Loads already cataloged assets
- Reads INFORMATION_SCHEMA for current dataset metadata
- Compares current metadata with registry metadata
- Identifies:
  - New tables
  - New columns
  - Modified assets
  - Missing metadata entries

### Activity Panel Actions

- Updating catalog for dataset
- Registry table location
- Update scope
- Reading existing assets from registry
- Reading INFORMATION_SCHEMA
- Diffing metadata

---

![X_3](/UI_Specs/X_3.png)

## Step 3.2 : Metadata Crawling and Diffing

The update process continues by:

- Crawling dataset metadata again
- Comparing crawled assets with registry entries
- Identifying only incremental changes
- Ignoring already cataloged assets
- Detecting schema changes in existing tables
- Detecting newly added columns
- Detecting modified column metadata
- Detecting datatype changes
- Detecting description changes

### Update Scenarios

#### Scenario 1 : Registry Table Does Not Exist

If data_catalog_registry does not exist:

- Agent automatically creates the data_catalog_registry table
- Agent crawls dataset metadata
- Agent inserts all discovered metadata into the registry
- Newly inserted metadata records are displayed in the X_5 result screen

#### Scenario 2 : New Table Added

If a new table is added in the dataset:

- Agent detects the new table from INFORMATION_SCHEMA
- Metadata is generated for the new table
- New row is inserted into data_catalog_registry
- Newly added records are displayed in the X_5 screen

#### Scenario 3 : Existing Table Metadata Modified

If metadata of an existing table changes:

Examples:

- Column datatype changed
- Column description changed
- Table description changed
- Nullable flag changed
- Column renamed
- Number of columns increased
- Number of columns decreased

Then:

- Agent detects metadata differences
- Agent updates registry metadata
- Agent inserts updated metadata entry
- Only updated records are displayed in the X_5 screen

Example:

```text
Old Datatype:
customer_id STRING

New Datatype:
customer_id INT64

Detected Change:
Datatype modified
```

#### Scenario 4 : No Changes

If no metadata changes are detected:

- No new rows inserted
- No updates performed
- Registry remains unchanged

The UI should display:

```text
Registry is up to date

<project_id>.<dataset>.data_catalog_registry — 0 total rows
```

### Backend Logic

```text
IF data_catalog_registry NOT EXISTS
    CREATE registry table
    INSERT all discovered metadata

ELSE
    FOR each asset in INFORMATION_SCHEMA
        IF asset NOT EXISTS in registry
            INSERT new metadata row

        ELSE IF column added
            UPDATE registry metadata

        ELSE IF column removed
            UPDATE registry metadata

        ELSE IF datatype changed
            UPDATE registry metadata

        ELSE IF metadata changed
            UPDATE registry metadata

        ELSE
            SKIP asset
```

---

![X_4](/UI_Specs/X_4.png)

## Step 3.3 : Registry Already Up To Date

If no changes are detected:

- No new rows are inserted
- Registry remains unchanged
- System displays success state with no-op update

### Activity Panel Messages

- Registry already has all assets
- Nothing new to add
- Update completed successfully

### UI State

- Display success banner
- Show zero rows inserted
- Show “Registry is up to date”

---

![X_5](/UI_Specs/X_5.png)

# Functional Flow Summary

## Build New Catalog

Used when registry does not exist.

Flow:

1. Select project
2. Select dataset
3. Select registry location
4. Crawl metadata
5. Create registry table
6. Insert all discovered metadata

---

## Update Existing Catalog

Used when registry already exists.

Flow:

1. Identify dataset
2. Read existing registry
3. Crawl INFORMATION_SCHEMA again
4. Compare registry vs current metadata
5. Insert only new or changed assets
6. Skip unchanged assets
7. Display update summary

---

# Important Notes

## Registry Table

Default registry table:

```text
<project_id>.<dataset>.data_catalog_registry
```

## INFORMATION_SCHEMA Usage

Agent reads metadata from:

```sql
INFORMATION_SCHEMA.TABLES
INFORMATION_SCHEMA.COLUMNS
```

## Incremental Update Strategy

The update workflow is optimized to:

- Avoid duplicate entries
- Avoid full reprocessing
- Insert only delta changes
- Reduce BigQuery compute cost
- Improve update performance

---

# Final Goal

The Update Existing Catalog feature ensures that:

- Registry always remains synchronized with BigQuery datasets
- New tables and columns are automatically cataloged
- Existing metadata remains reusable
- Only incremental changes are processed
- Metadata maintenance becomes efficient and scalable
