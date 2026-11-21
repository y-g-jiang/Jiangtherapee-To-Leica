typedef unsigned int uint32_t;
typedef __SIZE_TYPE__ size_t;
extern int _NSGetExecutablePath(char *, uint32_t *);
extern char *realpath(const char *, char *);
extern char *strrchr(const char *, int);
extern int snprintf(char *, size_t, const char *, ...);
extern void *calloc(size_t, size_t);
extern int execv(const char *, char *const []);
extern int setenv(const char *, const char *, int);

int main(int count, char **arguments) {
    char executable[4096], resolved[4096], python[4096], app[4096], plugins[4096];
    uint32_t size = sizeof(executable);
    if (_NSGetExecutablePath(executable, &size) || !realpath(executable, resolved)) return 1;
    char *last = strrchr(resolved, '/');
    if (!last) return 1;
    *last = 0;
    if (snprintf(python, sizeof(python), "%s/../Resources/python/bin/python3.10", resolved) >= sizeof(python)) return 1;
    if (snprintf(app, sizeof(app), "%s/../Resources/studio/app.py", resolved) >= sizeof(app)) return 1;
    if (snprintf(plugins, sizeof(plugins), "%s/../Resources/python/lib/python3.10/site-packages/PySide6/Qt/plugins/platforms", resolved) >= sizeof(plugins)) return 1;
    setenv("QT_QPA_PLATFORM_PLUGIN_PATH", plugins, 1);
    char **command = calloc((size_t)count+7, sizeof(char *));
    if (!command) return 1;
    command[0]=python;command[1]="-E";command[2]="-s";command[3]="-B";command[4]=app;
    for (int index=1; index<count; index++) command[index+4]=arguments[index];
    execv(python, command);
    return 1;
}
