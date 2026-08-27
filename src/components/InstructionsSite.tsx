import React from 'react';
import Tabs from "@theme/Tabs";
import TabItem from "@theme/TabItem";
import ThemeCodeBlock from '@theme/CodeBlock';
// import Admonition from '@theme/Admonition';
import Details from '@theme/Details';
import Link from '@docusaurus/Link';

// import {VerifyDev1,VerifyDev1} from '@site/src/components/InstructionsSite';
/*
<Link to="/docs/stm32cubemx">STM32CubeMX</Link>
<Link to="/docs/stm32cubeclt">STM32CubeCLT</Link>
<Link to="/docs/stm32cubeprg">STM32CubeProg</Link>
<Link to="/docs/stm32cubemon">STM32CubeMonitor</Link>
<Link to="/docs/stm32cubeide">STM32CubeIDE</Link>
<Link to="/docs/git">git</Link>
<Link to="/docs/github-cli">GitHub CLI</Link>
<Link to="/docs/vs-code">Visual Studio Code</Link>
<Link to="/docs/stm32cubetools">STM32Cube Tools</Link>
*/

// import {VerifyDev1} from '@site/src/components/InstructionsSite';
// <!-- Verifique o seu ambiente dev, git, gh e code -->
// <VerifyDev1 />
export function VerifyDev1() {
    return (
        <div>
            <Details summary={<summary>Verifique o seu ambiente de desenvolvimento!</summary>}>
                <p>Versão do <Link to="/docs/git">git</Link> e configurações:</p>
                <ThemeCodeBlock className="language-bash">
                    git --version
                </ThemeCodeBlock>
                <ThemeCodeBlock className="language-bash">
                    git config --list --show-origin
                </ThemeCodeBlock>

                <p>Versão do <Link to="/docs/github-cli">GitHub CLI</Link> e status de login:</p>
                <ThemeCodeBlock className="language-bash">
                    gh --version
                </ThemeCodeBlock>
                <ThemeCodeBlock className="language-bash">
                    gh auth status
                </ThemeCodeBlock>

                <p>Versão do <Link to="/docs/vs-code-intro">Visual Studio Code</Link> e extensões instaladas:</p>
                <ThemeCodeBlock className="language-bash">
                    code -v
                </ThemeCodeBlock>
                <ThemeCodeBlock className="language-bash">
                    code --list-extensions --profile "ESP32IO"
                </ThemeCodeBlock>
            </Details>
        </div >
    );
}

// import {VerifyDev2} from '@site/src/components/InstructionsSite';
// <!-- Verifique o seu ambiente dev, git, gh, code, gcc e gdb -->
// <VerifyDev2 />
export function VerifyDev2() {
    return (
        <div>
            <Details summary={<summary>Verifique o seu ambiente de desenvolvimento!</summary>}>
                <p>Versão do <Link to="/docs/git">git</Link> e configurações:</p>
                <ThemeCodeBlock className="language-bash">
                    git --version
                </ThemeCodeBlock>
                <ThemeCodeBlock className="language-bash">
                    git config --list --show-origin
                </ThemeCodeBlock>

                <p>Versão do <Link to="/docs/github-cli">GitHub CLI</Link> e status de login:</p>
                <ThemeCodeBlock className="language-bash">
                    gh --version
                </ThemeCodeBlock>
                <ThemeCodeBlock className="language-bash">
                    gh auth status
                </ThemeCodeBlock>

                <p>Versão do <Link to="/docs/vs-code-intro">Visual Studio Code</Link> e extensões instaladas:</p>
                <ThemeCodeBlock className="language-bash">
                    code -v
                </ThemeCodeBlock>
                <ThemeCodeBlock className="language-bash">
                    code --list-extensions --profile "STM32"
                </ThemeCodeBlock>

                <p>Versão do gcc e gdb instaladas:</p>
                <ThemeCodeBlock className="language-bash">
                    gcc --version
                </ThemeCodeBlock>
                <ThemeCodeBlock className="language-bash">
                    gbd --version
                </ThemeCodeBlock>
            </Details>
        </div >
    );
}

// import {GitConfig} from '@site/src/components/InstructionsSite';
// <!-- Configure o git -->
// <GitConfig />
export function GitConfig() {
    return (
        <div>
            <Details summary={<summary>Configure a ferramenta git</summary>}>
                <p>Configure o nome de usuário para todos os repositórios locais ligados às suas transações de commit:</p>
                <ThemeCodeBlock className="language-bash">
                    git config --global user.name "Your Name"
                </ThemeCodeBlock>

                <p> Configure o email de usuário para todos os repositórios locais ligados às suas transações de commit:</p>
                <ThemeCodeBlock className="language-bash">
                    git config --global user.email "you@example.com"
                </ThemeCodeBlock>

                <p>É recomendado verificar se a instalação do seu Git não está realizando nenhuma transformação entre LFs e CRLFs.</p>
                <ThemeCodeBlock className="language-bash">
                    git config --global core.autocrlf false
                </ThemeCodeBlock>

                <p>Configure o <Link to="/docs/git">git</Link> para usar o <Link to="/docs/vs-code-intro">Visual Studio Code</Link> como editor padrão para tarefas como escrever mensagens de commit ou rebases interativos</p>
                <ThemeCodeBlock className="language-bash">
                    git config --global core.editor "code --wait"
                </ThemeCodeBlock>

                <p>Habilite a coloração automática da saída da linha de comando do <Link to="/docs/git">Git</Link>:</p>
                <ThemeCodeBlock className="language-bash">
                    git config --global color.ui auto
                </ThemeCodeBlock>

                <p>Configura o <Link to="/docs/git">Git</Link> para usar main como o nome do branch padrão sempre que você inicializar um novo repositório localmente:</p>
                <ThemeCodeBlock className="language-bash">
                    git config --global init.defaultBranch main
                </ThemeCodeBlock>

                <p>Liste as configurações aplicadas:</p>
                <ThemeCodeBlock className="language-bash">
                    git config --list --show-origin
                </ThemeCodeBlock>
            </Details>
        </div >
    );
}

// import {DevTools} from '@site/src/components/InstructionsSite';
// <!-- Lista de Ferramentas de Desenvolvimento -->
// <DevTools />
export function DevTools() {
    return (
        <Tabs>
            <TabItem value="git-scm" label="Git SCM" default>
                <p><b>O <Link to="/docs/git">Git</Link> é a ferramenta de gerenciamento de código-fonte mais utilizada por desenvolvedores profissionais.</b></p>
                <ul>
                    <li>O <a href="https://git-scm.com/downloads/win" target="_blank">Git</a> é um sistema de controle de versão distribuído gratuito e de código aberto, projetado para lidar com tudo, desde projetos pequenos até muito grandes, com rapidez e eficiência.
                    </li>
                </ul>
                <ThemeCodeBlock className="language-bash">
                    winget install --id Git.Git -e --source winget
                </ThemeCodeBlock>
                <p>Configurações do <Link to="/docs/git">git</Link>:</p>
                <ThemeCodeBlock className="language-bash">
                    git config --list --show-origin
                </ThemeCodeBlock>
            </TabItem>
            <TabItem value="gh" label="GitHub CLI">
                <p><b>O <Link to="/docs/github-cli">GitHub CLI</Link> traz o GitHub para o seu terminal.</b></p>
                <ul>
                    <li>O <a href="https://cli.github.com/" target="_blank">GitHub CLI</a> é uma ferramenta de linha de comando que permite interagir com o GitHub diretamente pelo terminal. Está disponível para Windows, macOS e Linux.
                    </li>
                </ul>
                <ThemeCodeBlock className="language-bash">
                    winget install --id GitHub.cli -e --source winget
                </ThemeCodeBlock>
                <p>Status de login do <Link to="/docs/github-cli">GitHub CLI</Link>:</p>
                <ThemeCodeBlock className="language-bash">
                    gh auth status
                </ThemeCodeBlock>
            </TabItem>
            <TabItem value="GitHubDesktop" label="GitHub Desktop">
                <p><b>O <Link to="/docs/github-desktop">GitHub Desktop</Link> é uma maneira simples de usar o Git e o GitHub no seu computador.</b></p>
                <ul>
                    <li>O <a href="https://desktop.github.com/download/" target="_blank">GitHub Desktop</a> é um cliente Git gratuito e de código aberto para Windows e macOS. Ele permite gerenciar seus repositórios Git e colaborar com outras pessoas.
                    </li>
                </ul>
                <ThemeCodeBlock className="language-bash">
                    winget install -e --id GitHub.GitHubDesktop
                </ThemeCodeBlock>
            </TabItem>
            <TabItem value="vscode" label="VS Code">
                <p><b><Link to="/docs/vs-code-intro">Visual Studio Code</Link>: IDE e Editor de Código para Desenvolvimento de Software.</b></p>
                <ul>
                    <li>O <a href="https://code.visualstudio.com/download" target="_blank">VS Code</a> é um editor de código-fonte gratuito criado pela Microsoft para Windows, Linux e macOS. Inclui suporte para depuração, controle Git integrado, realce de sintaxe, conclusão inteligente de código, snippets e refatoração de código.
                    </li>
                </ul>
                <ThemeCodeBlock className="language-bash">
                    winget install --id Microsoft.VisualStudioCode -e --source winget
                </ThemeCodeBlock>
                <p>Extensões instaladas do <Link to="/docs/vs-code-intro">Visual Studio Code</Link> para o perfil ESP32IO:</p>
                <ThemeCodeBlock className="language-bash">
                    code --list-extensions --profile "ESP32IO"
                </ThemeCodeBlock>
                <p>Inicie o projeto no PlatformIO:</p>
                <ThemeCodeBlock className="language-bash">
                    pio project init -b esp32dev -O "framework=arduino" -O "monitor_speed=115200" --sample-code
                </ThemeCodeBlock>
            </TabItem>
            <TabItem value="esp32-wokwi" label="Wokwi">
                <p><b><Link to="/docs/category/wokwi">Wokwi para VSCode</Link>: Simulador de sistemas embarcados e IoT com suporte para ESP32, Arduino e Raspberry Pi Pico.</b></p>
                <ul>
                    <li><a href="https://marketplace.visualstudio.com/items?itemName=Wokwi.wokwi-vscode" target="_blank">Wokwi para VSCode</a> Seu código nunca sai do seu computador - o Wokwi executa a simulação dentro do VS Code, utilizando os binários de firmware do seu projeto.
                    </li>
                </ul>
                <ThemeCodeBlock className="language-bash">
                    code --install-extension wokwi.wokwi-vscode --profile "ESP32IO"
                </ThemeCodeBlock>
                <ul><li><a href="https://wokwi.com/license?v=3.6.1&r=UserRequest&s=v" target="_blank">Wokwi for Visual Studio Code.</a></li></ul>
            </TabItem>
            <TabItem value="esp32-platformio" label="PlatformIO">
                <p><b><Link to="/docs/platformio-intro">PlatformIO IDE para VSCode</Link>: Sua porta de entrada para a excelência no desenvolvimento de software embarcado.</b></p>
                <ul>
                    <li><a href="https://marketplace.visualstudio.com/items?itemName=platformio.platformio-ide" target="_blank">PlatformIO IDE para VSCode</a> Desbloqueie o verdadeiro potencial do desenvolvimento de software embarcado com o ecossistema colaborativo do PlatformIO, adotando princípios declarativos, metodologias orientadas a testes e toolchains modernas para um sucesso incomparável.
                    </li>
                </ul>
                <ThemeCodeBlock className="language-bash">
                    code --install-extension platformio.platformio-ide --profile "ESP32IO"
                </ThemeCodeBlock>
                <p><ul><li>Instale a plataforma espressif32:</li></ul></p>
                <ThemeCodeBlock className="language-bash">
                    {`pio platform install espressif32`}
                </ThemeCodeBlock>
                <p>Você precisa editar a variável de ambiente do sistema chamada <b>Path</b> e adicionar o caminho <b>%USERPROFILE%\.platformio\penv\Scripts\</b> no início da lista.</p>
                <p><ul><li>Inicie o projeto no PlatformIO:</li></ul></p>
                <ThemeCodeBlock className="language-bash">
                    {`pio project init -b esp32dev -O "framework=arduino" -O "monitor_speed=115200" --sample-code`}
                </ThemeCodeBlock>
            </TabItem>
            <TabItem value="esp32-drivers" label="Drivers">
                <ol>
                    <li>Conecte o ESP32 ao computador via USB.</li>
                    <li>
                        Abra o <b>Gerenciador de Dispositivos</b> (clique com o botão direito no Menu Iniciar &rarr; Gerenciador de Dispositivos).
                    </li>
                    <li>Expanda a seção <b>Portas (COM e LPT)</b>.</li>
                    <li>
                        Procure por um dispositivo similar a:
                        <ul>
                            <li>
                                <a href="https://www.silabs.com/software-and-tools/usb-to-uart-bridge-vcp-drivers?tab=downloads" target="_blank" rel="noopener noreferrer">
                                    Silicon Labs CP210x USB to UART Bridge (COMx)
                                </a>
                            </li>
                            <li>
                                <a href="https://www.wch-ic.com/downloads/CH341SER_ZIP.html" target="_blank" rel="noopener noreferrer">
                                    Driver Windows CH340/CH341 USB para porta serial
                                </a>
                            </li>
                            <li>FTDI ou &ldquo;Dispositivo Serial USB (COMx)&rdquo;</li>
                        </ul>
                    </li>
                </ol>
                <p>
                    Anote o número da porta (ex: <b>COM4</b>, <b>COM6</b>, <b>COM12</b>). Se não aparecer nenhuma porta nova, o driver não está instalado. Baixe o driver correspondente (CP210x ou CH340) no site do fabricante da placa.
                </p>
                <ThemeCodeBlock className="language-bash">
                    pip install esptool
                </ThemeCodeBlock>
                <ThemeCodeBlock className="language-bash">
                    esptool chip-id
                </ThemeCodeBlock>
            </TabItem>
        </Tabs>
    );
}

// import {GitLogOut} from '@site/src/components/InstructionsSite';
// <!-- Logout do seu ambiente dev, git e gh -->
// <GitLogOut />
export function GitLogOut() {
    return (
        <div>
            <Details summary={<summary>Faça Logout do seu ambiente de desenvolvimento!</summary>}>
                <p>Para o <Link to="/docs/git">git</Link> "esquecer" suas informações salvas:</p>
                <ThemeCodeBlock className="language-bash">
                    git credential-manager erase
                </ThemeCodeBlock>
                <p>Ou liste suas credenciais:</p>
                <ThemeCodeBlock className="language-bash">
                    cmdkey /list | findstr "github"
                </ThemeCodeBlock>
                <p>Exclua a credencial:</p>
                <ThemeCodeBlock className="language-bash">
                    cmdkey /delete:git:https://github.com
                </ThemeCodeBlock>
                <p>Logout do <Link to="/docs/github-cli">GitHub CLI</Link>:</p>
                <ThemeCodeBlock className="language-bash">
                    gh auth logout
                </ThemeCodeBlock>
            </Details>
        </div >
    );
}


// import {GitCommit} from '@site/src/components/InstructionsSite';
// <!-- Configure o git -->
// <GitCommit />
export function GitCommit() {
    return (
        <div>
            <Details summary={<summary>Como fazer commit da atualizações</summary>}>
                <p>Verifique o status do repositório:</p>
                <ThemeCodeBlock className="language-bash">
                    git status
                </ThemeCodeBlock>

                <p>Adicione os arquivos modificados:</p>
                <ThemeCodeBlock className="language-bash">
                    git add .
                </ThemeCodeBlock>

                <p>Realize o <Link to="/docs/git-best-practices">commit</Link> das alterações:</p>
                <ThemeCodeBlock className="language-bash">
                    git commit -m "Descrição breve das alterações realizadas!"
                </ThemeCodeBlock>

                <p>Envie para o repositório remoto (GitHub):</p>
                <ThemeCodeBlock className="language-bash">
                    git push
                </ThemeCodeBlock>

                <p>Vizualize o log de alterações:</p>
                <ThemeCodeBlock className="language-bash">
                    git log
                </ThemeCodeBlock>

                <p>Vizualize no GitHub:</p>
                <ThemeCodeBlock className="language-bash">
                    gh repo view --web
                </ThemeCodeBlock>
            </Details>
        </div >
    );
}

// import {NewBranch} from '@site/src/components/InstructionsSite';
// <!-- Como criar uma nova branch -->
// <NewBranch />
export function NewBranch() {
    return (
        <div>
            <Details summary={<summary>Como criar uma nova branch</summary>}>
                <p>Verifique o status do repositório:</p>
                <ThemeCodeBlock className="language-bash">
                    git status
                </ThemeCodeBlock>

                <p>Crie uma nova branch:</p>
                <ThemeCodeBlock className="language-bash">
                    git branch new-feature
                </ThemeCodeBlock>

                <p>Altere para a nova branch:</p>
                <ThemeCodeBlock className="language-bash">
                    git checkout new-feature
                </ThemeCodeBlock>

                <p>Mostra as branches:</p>
                <ThemeCodeBlock className="language-bash">
                    git branch
                </ThemeCodeBlock>

                <p>Envie a nova branch para o repositório remoto:</p>
                <ThemeCodeBlock className="language-bash">
                    git push --set-upstream origin new-feature
                </ThemeCodeBlock>

                <p>Compara as branches:</p>
                <ThemeCodeBlock className="language-bash">
                    git diff main new-feature
                </ThemeCodeBlock>

                <p>Retorna para a branch principal:</p>
                <ThemeCodeBlock className="language-bash">
                    git checkout main
                </ThemeCodeBlock>

                <p>Mescla a branch nova na branch principal:</p>
                <ThemeCodeBlock className="language-bash">
                    git merge new-feature
                </ThemeCodeBlock>

                <p>Vizualize no GitHub:</p>
                <ThemeCodeBlock className="language-bash">
                    gh repo view --web
                </ThemeCodeBlock>
            </Details>
        </div >
    );
}
