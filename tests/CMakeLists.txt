# Tests configuration

# Test sources (will add as we create components)
set(TEST_SOURCES
    # test_sermon.cpp
    # test_status_tracker.cpp
    # test_sermon_scanner.cpp
    # test_audio_processor.cpp
    # test_transcriber.cpp
    # test_translator.cpp
    # test_tts_engine.cpp
)

# Only build tests if we have test sources
if(TEST_SOURCES)
    # Create test executable
    add_executable(sermon_voices_tests ${TEST_SOURCES})

    # Link libraries
    target_link_libraries(sermon_voices_tests
        PRIVATE
            nlohmann_json
            cpp_httplib
            inja
    )

    # Include directories
    target_include_directories(sermon_voices_tests
        PRIVATE
            ${CMAKE_SOURCE_DIR}/include
            ${CMAKE_SOURCE_DIR}/src
    )

    # Add test
    add_test(NAME sermon_voices_tests COMMAND sermon_voices_tests)
else()
    message(STATUS "No test sources defined yet")
endif()
