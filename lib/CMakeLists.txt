# Third-party libraries

# nlohmann/json - Header-only JSON library
if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/json/include)
    add_library(nlohmann_json INTERFACE)
    target_include_directories(nlohmann_json INTERFACE ${CMAKE_CURRENT_SOURCE_DIR}/json/include)
    message(STATUS "Found nlohmann/json")
else()
    message(WARNING "nlohmann/json not found. Run 'make setup-cpp' to download.")
endif()

# cpp-httplib - Header-only HTTP library
if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/cpp-httplib)
    add_library(cpp_httplib INTERFACE)
    target_include_directories(cpp_httplib INTERFACE ${CMAKE_CURRENT_SOURCE_DIR}/cpp-httplib)
    message(STATUS "Found cpp-httplib")
else()
    message(WARNING "cpp-httplib not found. Run 'make setup-cpp' to download.")
endif()

# inja - Header-only template engine
if(EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/inja/include)
    add_library(inja INTERFACE)
    target_include_directories(inja INTERFACE ${CMAKE_CURRENT_SOURCE_DIR}/inja/include)
    target_link_libraries(inja INTERFACE nlohmann_json)
    message(STATUS "Found inja")
else()
    message(WARNING "inja not found. Run 'make setup-cpp' to download.")
endif()
