# PolyForge
Git structure 
main              # production-ready code only. never commit directly here.
develop           # integration branch. all features merge here first.
feature/<name>    # one branch per component being built
fix/<name>        # bug fixes
chore/<name>      # non-code work (docs, config, dependencies)