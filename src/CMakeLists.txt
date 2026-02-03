# Source files
set(SERMON_VOICES_SOURCES
    main.cpp
    # sermon.cpp
    # status_tracker.cpp
    # sermon_scanner.cpp
    # audio_processor.cpp
    # transcriber.cpp
    # translator.cpp
    # tts_engine.cpp
    # voice_cloner.cpp
    # document_generator.cpp
    # web_server.cpp
    # utils.cpp
)

# Create executable
add_executable(sermon_voices ${SERMON_VOICES_SOURCES})

# Link libraries
target_link_libraries(sermon_voices
    PRIVATE
        nlohmann_json
        cpp_httplib
        inja
)

# Include directories
target_include_directories(sermon_voices
    PRIVATE
        ${CMAKE_SOURCE_DIR}/include
)

# Platform-specific settings
if(APPLE)
    # macOS specific settings
    target_compile_definitions(sermon_voices PRIVATE MACOS)
endif()

# Installation
install(TARGETS sermon_voices
    RUNTIME DESTINATION bin
)
