# Superwebby AUR-style packages (1.0.0)

- `superwebby/` — build from the source tarball on the GitHub release
- `superwebby-bin/` — install the prebuilt x86_64 tarball from the same release

```bash
# from source
cd superwebby && makepkg -si

# or the prebuilt binary
cd superwebby-bin && makepkg -si
```

The PKGBUILDs download their `source=` tarballs from
https://github.com/superwebby/superwebby/releases/tag/v1.0.0
so they need network access, or you can place the matching tarball next to
the PKGBUILD and temporarily drop the `::https://...` suffix from `source=`.
