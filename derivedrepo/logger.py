class Logger:
    def log_checkout(self, commit):
        pass

    def log_check_commit_to_derive(self, commit):
        pass

    def log_commit_already_derived(self, commit):
        pass

    def log_derive_start(self, commit):
        pass

    def log_derive_finished(self, commit, output_dir, notes):
        pass

    def log_derive_failed(self, commit, notes):
        pass

    def log_derivative_stored(self, commit):
        pass