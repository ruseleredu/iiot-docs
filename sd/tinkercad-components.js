const fs = require("fs");
const vm = require("vm");

const code = fs.readFileSync("scripts/circuits-compiled.js", "utf8");

const modules = {};
const exportsCollected = [];

const sandbox = {
    window: {},
    self: {},
    console,
};

// Fake webpack loader hook
sandbox.webpackChunk = [];
sandbox.webpackChunk.push = function (chunk) {
    const moreModules = chunk[1];

    for (const id in moreModules) {
        try {
            const moduleFunc = moreModules[id];
            const module = { exports: {} };

            moduleFunc(module, module.exports, () => { });

            if (module.exports && module.exports.name) {
                exportsCollected.push(module.exports);
            }
        } catch (err) {
            // ignore broken modules
        }
    }
};

vm.runInNewContext(code, sandbox);

// Save JSON
fs.writeFileSync("components.json", JSON.stringify(exportsCollected, null, 2));