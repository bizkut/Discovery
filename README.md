# Discovery: Customizable Minecraft Agent Model

## About Discovery

Discovery is an advanced Minecraft agent model based on [MineDojo Voyager](https://github.com/MineDojo/Voyager), enhanced with [LangFlow](https://github.com/logspace-ai/langflow) integration to enable greater customization and flexibility. While Voyager pioneered LLM-powered embodied agents in Minecraft, Discovery takes this concept further by allowing researchers and developers to easily modify agent behaviors, adapt different LLM models, and create custom skill libraries through an intuitive flow-based interface.

### Key Features

- **LangFlow Integration**: Visually design and customize agent behaviors without deep coding knowledge
- **Model Flexibility**: Easily swap between different LLM providers (OpenAI, Anthropic, local models)
- **Enhanced Customization**: Modify prompts, skills, and exploration strategies through a visual interface
- **Docker Ready**: Simplified deployment with containerized environment
- **Cross-Platform**: Works seamlessly on Windows, macOS, and Linux

## Docker Installation

Discovery runs entirely in Docker, making setup simple and consistent across platforms.

### Prerequisites

- [Docker](https://www.docker.com/products/docker-desktop/) and Docker Compose
- Minecraft Java Edition (version 1.19.0)
- OpenAI API key or other supported LLM provider credentials

### Setup Instructions

1. **Clone the repository**
   ```bash
   git clone https://github.com/[your-username]/Discovery.git
   cd Discovery
   ```

2. **Configure environment variables**
   ```bash
   cp .env.example .env
   ```
   
   Edit the `.env` file with your API keys and preferences:
   ```
   # Minecraft connection information
   MINECRAFT_PORT=25565
   MINECRAFT_HOST=host.docker.internal

   # OpenAI API information
   OPENAI_API_KEY=your_openai_api_key_here

   # Azure Minecraft authentication (if needed)
   CLIENT_ID=your_client_id_here
   REDIRECT_URL=https://127.0.0.1/auth-response
   SECRET_VALUE=your_secret_value_here
   ```

3. **Install Minecraft Mods**
   
   Discovery requires specific Fabric mods to function properly:
   1. Install [Fabric Loader](https://fabricmc.io/use/installer/) (recommended: fabric-loader-0.14.18-1.19)
   2. Download and install the following mods to your Minecraft mods folder:
      - [Fabric API](https://modrinth.com/mod/fabric-api/version/0.58.0+1.19)
      - [Mod Menu](https://cdn.modrinth.com/data/mOgUt4GM/versions/4.0.4/modmenu-4.0.4.jar)
      - [Complete Config](https://www.curseforge.com/minecraft/mc-mods/completeconfig/download/3821056)
      - [Multi Server Pause](https://www.curseforge.com/minecraft/mc-mods/multiplayer-server-pause-fabric/download/3822586)
      - [Better Respawn](https://github.com/xieleo5/better-respawn/tree/1.19) (requires manual build)

4. **Build and start the Docker container**
   ```bash
   docker-compose up -d
   ```
   
   This will:
   - Build the Docker image with all necessary dependencies
   - Start the container in the background
   - Expose ports for LangFlow (7860), ChatUI (7850), and Minecraft (?)

5. **Start Minecraft and enable LAN**
   - Launch Minecraft client on your host machine with the Fabric profile
   - Create a new world in Creative mode with Peaceful difficulty
   - Press Esc, select "Open to LAN"
   - Enable cheats and start the LAN world

6. **Access the LangFlow interface**
   
   Open your browser and navigate to:
   ```
   http://localhost:7860
   ```
   
   This opens the LangFlow interface where you can customize and run your Discovery agent.

7. **Run Discovery**
   ```bash
   docker exec -it discovery python3 run_voyager.py
   ```

   The agent will connect to your Minecraft world and begin operating according to your configured workflow.

## Using LangFlow to Customize Your Agent

The LangFlow interface allows you to visually customize your agent:

1. **Import a workflow** from the `langflow_json` directory
2. **Modify components** by dragging and connecting nodes
3. **Adjust parameters** such as exploration radius, skill priorities, or LLM settings
4. **Save your custom workflow** for future use
5. **Deploy** your agent directly from the interface

## Important Notes

- The Minecraft client must be running on your host machine, not in Docker
- Always start Minecraft and open to LAN **before** running Discovery
- If connection issues occur, check:
  - Your firewall settings
  - The MINECRAFT_PORT in your .env file matches the LAN port Minecraft is using
  - Host settings in docker-compose.yml
- Ensure mod versions match exactly as specified

## License

This project is available under [Research and Development License - Non-Commercial Use Only](LICENSE).

**Disclaimer**: This project is strictly for research purposes and not an official product.
