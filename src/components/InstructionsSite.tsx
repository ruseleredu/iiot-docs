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
// <!-- List of Dev Tools -->
// <DevTools />
export function DevTools() {
    return (
        <Tabs>
            <TabItem value="git-scm" label="Git SCM" default>
                <p><b><Link to="/docs/git">Git</Link> is the most widely used source-code management tool among professional developers.</b></p>
                <ul>
                    <li><a href="https://git-scm.com/downloads/win" target="_blank">Git</a> is a free and open source distributed version control system designed to handle everything from small to very large projects with speed and efficiency.
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
                <p><b><Link to="/docs/github-cli">GitHub CLI</Link> brings GitHub to your terminal.</b></p>
                <ul>
                    <li><a href="https://cli.github.com/" target="_blank">GitHub CLI</a> is a command line tool that allows you to interact with GitHub from the command line. It is available for Windows, macOS, and Linux.
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
                <p><b><Link to="/docs/github-desktop">GitHub Desktop</Link> is a simple way to use Git and GitHub on your computer.</b></p>
                <ul>
                    <li><a href="https://desktop.github.com/download/" target="_blank">GitHub Desktop</a> is a free, open-source Git client for Windows and macOS. It allows you to manage your Git repositories and collaborate with others.
                    </li>
                </ul>
                <ThemeCodeBlock className="language-bash">
                    winget install -e --id GitHub.GitHubDesktop
                </ThemeCodeBlock>
            </TabItem>
            <TabItem value="vscode" label="VS Code">
                <p><b><Link to="/docs/vs-code-intro">Visual Studio Code</Link>: IDE and Code Editor for Software Development.</b></p>
                <ul>
                    <li><a href="https://code.visualstudio.com/download" target="_blank">VS Code</a> is a free source-code editor made by Microsoft for Windows, Linux and macOS. It includes support for debugging, embedded Git control, syntax highlighting, intelligent code completion, snippets, and code refactoring.
                    </li>
                </ul>
                <ThemeCodeBlock className="language-bash">
                    winget install --id Microsoft.VisualStudioCode -e --source winget
                </ThemeCodeBlock>
                <p>Extensões instaladas do <Link to="/docs/vs-code-intro">Visual Studio Code</Link> para o perfil STM32:</p>
                <ThemeCodeBlock className="language-bash">
                    code --list-extensions --profile "ESP32IO"
                </ThemeCodeBlock>
            </TabItem>
            <TabItem value="esp32-wokwi" label="Wokwi">
                <p><b><Link to="/docs/category/wokwi">Wokwi for VSCode</Link>: Embedded systems and IoT simulator supporting ESP32, Arduino, and the Raspberry Pi Pico.</b></p>
                <ul>
                    <li><a href="https://marketplace.visualstudio.com/items?itemName=Wokwi.wokwi-vscode" target="_blank">Wokwi for VSCode</a> Your code never leaves your computer - Wokwi runs the simulation inside VS Code, using the firmware binaries from your project.
                    </li>
                </ul>
                <ThemeCodeBlock className="language-bash">
                    code --install-extension wokwi.wokwi-vscode --profile "ESP32IO"
                </ThemeCodeBlock>
            </TabItem>
            <TabItem value="esp32-platformio" label="PlatformIO">
                <p><b><Link to="/docs/platformio-intro">PlatformIO IDE for VSCode</Link>: Your Gateway to Embedded Software Development Excellence.</b></p>
                <ul>
                    <li><a href="https://marketplace.visualstudio.com/items?itemName=platformio.platformio-ide" target="_blank">PlatformIO IDE for VSCode</a> Unlock the true potential of embedded software development with PlatformIO’s collaborative ecosystem, embracing declarative principles, test-driven methodologies, and modern toolchains for unrivaled success.
                    </li>
                </ul>
                <ThemeCodeBlock className="language-bash">
                    code --install-extension platformio.platformio-ide --profile "ESP32IO"
                </ThemeCodeBlock>
                <p>You need to edit the system environment variable called <b>Path</b> and append <b>%USERPROFILE%\.platformio\penv\Scripts\</b> path in the beginning of the list.</p>

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
