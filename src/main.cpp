#include <iostream>
#include <string>
#include <vector>

// TODO: Add includes once headers are created
// #include "sermon_voices/sermon.hpp"
// #include "sermon_voices/status_tracker.hpp"
// #include "sermon_voices/sermon_scanner.hpp"
// ... etc

void print_usage(const char* program_name) {
    std::cout << "Sermon Voices - AI-powered sermon processing\n\n";
    std::cout << "Usage:\n";
    std::cout << "  " << program_name << " [options]\n\n";
    std::cout << "Options:\n";
    std::cout << "  --help              Show this help message\n";
    std::cout << "  --file <path>       Process a single sermon file\n";
    std::cout << "  --serve             Start web server\n";
    std::cout << "  --version           Show version information\n";
    std::cout << "\n";
    std::cout << "Default behavior (no options): Process all sermons in blobs/\n";
}

void print_version() {
    std::cout << "Sermon Voices v0.1.0\n";
    std::cout << "Built with C++17\n";
}

int main(int argc, char* argv[]) {
    // Parse command-line arguments
    bool serve_mode = false;
    std::string single_file;

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];

        if (arg == "--help" || arg == "-h") {
            print_usage(argv[0]);
            return 0;
        } else if (arg == "--version" || arg == "-v") {
            print_version();
            return 0;
        } else if (arg == "--serve") {
            serve_mode = true;
        } else if (arg == "--file" && i + 1 < argc) {
            single_file = argv[++i];
        } else {
            std::cerr << "Unknown option: " << arg << "\n";
            std::cerr << "Use --help for usage information\n";
            return 1;
        }
    }

    std::cout << "Sermon Voices - Starting...\n\n";

    if (serve_mode) {
        std::cout << "Web server mode\n";
        std::cout << "TODO: Start web server on http://localhost:8080\n";
        return 0;
    }

    if (!single_file.empty()) {
        std::cout << "Processing single file: " << single_file << "\n";
        std::cout << "TODO: Implement single file processing\n";
        return 0;
    }

    // Default: Process all sermons
    std::cout << "Processing all sermons in blobs/\n";
    std::cout << "TODO: Implement full pipeline\n";
    std::cout << "\nPhase 1 (Project Setup) is complete!\n";
    std::cout << "The build system is working correctly.\n";
    std::cout << "\nNext steps:\n";
    std::cout << "  1. Implement core data structures (Sermon, StatusTracker)\n";
    std::cout << "  2. Implement SermonScanner\n";
    std::cout << "  3. Implement AudioProcessor\n";
    std::cout << "  4. Continue with other pipeline components\n";

    return 0;
}
