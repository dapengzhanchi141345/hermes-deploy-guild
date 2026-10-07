#!/usr/bin/env node
import fs from 'node:fs'
import path from 'node:path'
import { createRequire } from 'node:module'
import { pathToFileURL } from 'node:url'
import { parseArgs } from 'node:util'
import { isMain } from './utils.mjs'
import { publishPackagingInputs } from './prepared-packaging.mjs'
import { ensureWindowsBundleTools } from './windows-bundle-tools.mjs'
import { prepareDmgbuild } from './prepare-dmgbuild.mjs'

/** @param {string} source @param {string} name @returns {string} */
export function pinnedPackageRoot(source, name) {
  const require = createRequire(path.join(source, 'apps/desktop/package.json'))
  const entry = require.resolve(name)
  let directory = path.dirname(entry)
  while (!fs.existsSync(path.join(directory, 'package.json'))) {
    const parent = path.dirname(directory)
    if (parent === directory) throw new Error(`Cannot locate installed ${name}`)
    directory = parent
  }
  const installed = JSON.parse(fs.readFileSync(path.join(directory, 'package.json'), 'utf8'))
  const lock = JSON.parse(fs.readFileSync(path.join(source, 'package-lock.json'), 'utf8'))
  const key = path.relative(source, directory).split(path.sep).join('/')
  if (!lock.packages?.[key] || lock.packages[key].version !== installed.version || installed.name !== name) {
    throw new Error(`Installed ${name} is not the source's lock-pinned package; prepare Node dependencies first`)
  }
  return directory
}

/** @param {string} target @returns {'x64' | 'arm64'} */
export function packagingTargetArch(target) {
  if (target === `${process.platform}-x64`) return 'x64'
  if (target === `${process.platform}-arm64`) return 'arm64'
  throw new Error(`Packaging preparation requires a same-OS x64/arm64 target, got ${target}`)
}

/** @param {string} from @param {string} to @returns {string} */
function copyTool(from, to) {
  fs.rmSync(to, { recursive: true, force: true })
  fs.cpSync(from, to, { recursive: true, verbatimSymlinks: true })
  return to
}

/**
 * Acquire bytes without signing credentials. Builder modules are loaded only
 * after the explicit cache root has been selected, before their lazy state runs.
 * @param {{ source: string, out: string, cache: string, target?: string, formats?: string[], dmgbuild?: string }} options
 * @returns {Promise<string>}
 */
async function preparePackagingTools({ source, out, cache, target = `${process.platform}-${process.arch}`, formats, dmgbuild }) {
  source = fs.realpathSync(source)
  out = path.resolve(out)
  cache = path.resolve(cache)
  fs.mkdirSync(out, { recursive: true })
  fs.rmSync(path.join(out, 'prepared.json'), { force: true })
  packagingTargetArch(target)
  const builderRoot = pinnedPackageRoot(source, 'app-builder-lib')
  pinnedPackageRoot(source, 'electron-builder')
  const require = createRequire(path.join(source, 'apps/desktop/package.json'))
  const config = require(path.join(source, 'apps/desktop/electron-builder.config.cjs'))
  formats ??= process.platform === 'win32' ? ['msix'] : process.platform === 'darwin' ? ['dmg', 'zip'] : ['AppImage']
  if (process.env.CUSTOM_DMGBUILD_PATH) throw new Error('Preparation must select the pinned dmgbuild supplier, not CUSTOM_DMGBUILD_PATH')
  const supported = process.platform === 'win32' ? ['dir', 'msix', 'zip'] : process.platform === 'darwin' ? ['dir', 'dmg', 'zip'] : ['dir', 'AppImage', 'deb', 'rpm', 'zip']
  if (formats.some(format => !supported.includes(format))) throw new Error(`Unsupported prepared package formats: ${formats.join(', ')}`)
  const dmg = formats.includes('dmg') ? prepareDmgbuild({ source, out, cache, binary: dmgbuild }) : null
  const previousCache = process.env.ELECTRON_BUILDER_CACHE
  process.env.ELECTRON_BUILDER_CACHE = path.join(cache, 'builder')
  try {
    return await acquirePackagingTools({ source, out, cache, target, formats, builderRoot, config, dmgbuild: dmg })
  } finally {
    if (previousCache === undefined) delete process.env.ELECTRON_BUILDER_CACHE
    else process.env.ELECTRON_BUILDER_CACHE = previousCache
  }
}

/**
 * @param {{ source: string, out: string, cache: string, target: string, formats: string[], builderRoot: string, config: import('app-builder-lib').Configuration, dmgbuild: string | null }} options
 * @returns {Promise<string>}
 */
async function acquirePackagingTools({ source, out, cache, target, formats, builderRoot, config, dmgbuild }) {
  /** @param {string} relative */
  const load = (relative) => import(pathToFileURL(path.join(builderRoot, 'dist', relative)).href)
  const [electronGet, sevenZip, icons] = await Promise.all([
    load('util/electronGet.js'), load('toolsets/7zip.js'), load('toolsets/icons.js'),
  ])
  const resourcesDir = path.join(source, 'apps/desktop', config.directories?.buildResources || 'build')
  const isDirOnly = (Array.isArray(formats) && formats.length === 1 && formats[0] === 'dir')
  const [archive, archiveTool, iconTools] = await Promise.all([
    electronGet.downloadElectronArtifactZip({ version: config.electronVersion, platformName: process.platform, arch: packagingTargetArch(target),
      artifactName: 'electron', cacheDir: path.join(cache, 'electron') }),
    isDirOnly ? Promise.resolve(null) : sevenZip.getPath7za(),
    isDirOnly ? Promise.resolve(null) : icons.getIconsToolsetPath(config.toolsets?.icons, resourcesDir),
  ])
  const electron = copyTool(archive, path.join(out, 'electron.zip'))
  /** @type {import('./prepared-packaging.mjs').PackagingToolsets} */
  const toolsets = {}
  if (!isDirOnly && archiveTool) toolsets.sevenZip = copyTool(path.dirname(path.dirname(archiveTool)), path.join(out, 'sevenZip'))
  if (!isDirOnly && iconTools) toolsets.icons = copyTool(iconTools, path.join(out, 'icons'))
  let windows = null
  if (process.platform === 'win32') {
    if (isDirOnly) {
      // dir-only unpack: no code signing or MSIX packaging, so the ATS dlib /
      // .NET runtime / makeappx are never executed. Provide a minimal winCodeSign
      // toolset from the already-installed rcedit + signtool packages so the exe
      // icon can still be embedded, and stub the sevenZip / icons toolsets that
      // readPackagingInputs admits but the dir build never uses. Avoids the
      // GitHub-blocked winCodeSign / 7zip / icons downloads entirely.
      const nm = path.dirname(builderRoot) // node_modules root
      const rceditBin = path.join(nm, 'rcedit', 'bin')
      const signtoolCandidates = [
        path.join(nm, '@electron', 'windows-sign', 'vendor', 'signtool.exe'),
        path.join(nm, 'electron-winstaller', 'vendor', 'signtool.exe'),
      ]
      const signtoolSrc = signtoolCandidates.find(p => fs.existsSync(p))
      const kitRoot = path.join(out, 'winCodeSign')
      fs.rmSync(kitRoot, { recursive: true, force: true })
      fs.mkdirSync(kitRoot, { recursive: true })
      fs.mkdirSync(path.join(kitRoot, 'x64'), { recursive: true })
      const rX64 = path.join(rceditBin, 'rcedit-x64.exe')
      const rX86 = path.join(rceditBin, 'rcedit.exe')
      if (fs.existsSync(rX64)) fs.copyFileSync(rX64, path.join(kitRoot, 'rcedit-x64.exe'))
      if (fs.existsSync(rX86)) fs.copyFileSync(rX86, path.join(kitRoot, 'rcedit-x86.exe'))
      if (signtoolSrc) fs.copyFileSync(signtoolSrc, path.join(kitRoot, 'x64', 'signtool.exe'))
      // placeholder makeappx — not executed for --dir, only required to exist by the validator
      fs.writeFileSync(path.join(kitRoot, 'x64', 'makeappx.exe'), '')
      toolsets.winCodeSign = kitRoot
      // Minimal sevenZip / icons toolsets so readPackagingInputs admits the dir build.
      const sevenZipDir = path.join(out, 'sevenZip')
      fs.rmSync(sevenZipDir, { recursive: true, force: true })
      fs.mkdirSync(sevenZipDir, { recursive: true })
      const iconsDir = path.join(out, 'icons')
      fs.rmSync(iconsDir, { recursive: true, force: true })
      fs.mkdirSync(iconsDir, { recursive: true })
      toolsets.sevenZip = sevenZipDir
      toolsets.icons = iconsDir
      // windows bundle-tools object: readPackagingInputs requires windows + dotnetRoot.
      const dotnetRoot = path.join(out, 'dotnet')
      fs.rmSync(dotnetRoot, { recursive: true, force: true })
      fs.mkdirSync(dotnetRoot, { recursive: true })
      fs.writeFileSync(path.join(dotnetRoot, 'dotnet.exe'), '')
      windows = {
        makeappx: path.join(kitRoot, 'x64', 'makeappx.exe'),
        signtool: path.join(kitRoot, 'x64', 'signtool.exe'),
        dlib: null,
        dotnetRoot,
      }
    } else {
      const builder = await load('toolsets/winCodeSign.js')
      const tools = await ensureWindowsBundleTools({ config, resourcesDir, signing: true, load: async () => builder, prepared: null })
      const kitRoot = copyTool(path.dirname(path.dirname(tools.makeappx)), path.join(out, 'winCodeSign'))
      if (!tools.dlib || !tools.dotnetRoot) throw new Error('Windows preparation requires the ATS dlib and paired .NET runtime')
      fs.cpSync(path.dirname(tools.dlib), path.join(kitRoot, path.basename(path.dirname(tools.signtool))), { recursive: true })
      const rcedit = await builder.getRceditBundle(config.toolsets?.winCodeSign, resourcesDir)
      fs.copyFileSync(rcedit.x64, path.join(kitRoot, 'rcedit-x64.exe'))
      fs.copyFileSync(rcedit.x86, path.join(kitRoot, 'rcedit-x86.exe'))
      const kit = path.join(kitRoot, path.basename(path.dirname(tools.makeappx)))
      windows = { makeappx: path.join(kit, 'makeappx.exe'), signtool: path.join(kit, 'signtool.exe'),
        dlib: path.join(kit, 'Azure.CodeSigning.Dlib.dll'), dotnetRoot: copyTool(tools.dotnetRoot, path.join(out, 'dotnet')) }
      toolsets.winCodeSign = kitRoot
    }
  }
  if (formats.includes('AppImage')) {
    const appimage = await load('toolsets/appimage.js')
    const { Arch } = await import(pathToFileURL(path.join(builderRoot, 'dist/index.js')).href)
    const tools = await appimage.getAppImageTools(config.toolsets?.appimage, Arch[packagingTargetArch(target)], resourcesDir)
    toolsets.appimage = copyTool(path.dirname(tools.mksquashfs), path.join(out, 'appimage'))
  }
  if (formats.some(format => format === 'deb' || format === 'rpm')) {
    const fpm = await load('toolsets/fpm.js')
    toolsets.fpm = copyTool(path.dirname(await fpm.getFpmPath(config.toolsets?.fpm, resourcesDir)), path.join(out, 'fpm'))
  }
  return publishPackagingInputs({ source, out, target, formats, electron, toolsets, windows, dmgbuild })
}

if (isMain(import.meta.url)) {
  const { values } = parseArgs({ options: {
    source: { type: 'string' }, out: { type: 'string' }, cache: { type: 'string' }, target: { type: 'string' },
    format: { type: 'string', multiple: true }, dmgbuild: { type: 'string' },
  } })
  if (!values.source || !values.out || !values.cache) throw new Error('Usage: prepare-packaging-tools.mjs --source REPO --out WORK/packager --cache CACHE/packager [--target same-OS-target] [--format FORMAT] [--dmgbuild PM_BINARY]')
  console.log(await preparePackagingTools({ source: values.source, out: values.out, cache: values.cache, target: values.target, formats: values.format, dmgbuild: values.dmgbuild }))
}
