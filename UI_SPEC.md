Step 1: Landing Page :
    Two Option :
    1.1. Build a new catalog  
    1.2. Update Existing Catalog 
    
    activity side panel to show agents actions streams

![landing_page](/UI_Specs/1_landing_page.png)


Step2 : (1.1 Extension  on Build a New catalog) When we click on Build a New catalog)

Step 2.1: User clicked on "Build a new catalog"
    ![2_1_create_a_new_catalog_1](/UI_Specs/2_1_create_a_new_catalog_1.png) 
    Action:

    User enters Project_id  and Click on "List Datasets" button
    Agent  uses bigquery to fetch datasets from BQ project

![2_1_users_enters_project_id](/UI_Specs/2_1_users_enters_project_id.png) 

![2_1_users_enters_project_id_activity](/UI_Specs/2_1_users_enters_project_id_activity.png) 

Step 2.2 : Which dataset to catalog?
based on previously entered project_id we will fetch all datasets under the project and display, user can enter continue to move forward or back to go to previous step

![2_2_which_dataset_to_pick.png](/UI_Specs/2_2_which_dataset_to_pick.png)

Step 2.3 User select dataset and click on Continue button 

default registry will be created at project-5c016d48-80d5-4534-b69.catalog_registry.data_catalog_registry


![2_3_dataset_picker](/UI_Specs/2_3_dataset_picker.png)

Step 3 change destination for registry location of catalog

need to create a registry table (/Users/chiragtagadiya/Downloads/MyProjects/ics/metadata-catalog-agent/infra/bq/data_catalog_registry.sql) in location user mentioned
![3_different_registry_location](/UI_Specs/3_different_registry_location.png)



Step 4 . Crawl and write

4.1 Once we confirm registry location, it starts building catalog
steps it follows
    4.1.1 -  if registry table is not created create it
![4_1_building_catalog_table](/UI_Specs/4_1_building_catalog.png)

![4_1_1_building_catalog_progress](/UI_Specs/4_1_1_building_catalog_progress.png)


    4.1.2 - Metadata generation is in progress
![4_1_2_generating_metadata_in_progress](/UI_Specs/4_1_2_generating_metadata_in_progress.png)

![4_1_3_registry_metadata_written](/UI_Specs/4_1_3_registry_metadata_written.png)

![4_1_4_show_written_metadata_detailed_view](/UI_Specs/4_1_4_show_written_metadata_detailed_view.png)


Once this flow is finished we will explore option on landing page(Update Existing Catalog )
Idea is if catalog already exists then we have to update assets which has changed or new. but that's not in this scope.