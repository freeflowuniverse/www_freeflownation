import gevent
from Jumpscale import j


FREEFLOW_ORG = "https://github.com/freeflownation/www_freeflownation"
REPOS = {
    "team": "https://github.com/threefoldfoundation/data_team/tree/master/team",
    "community": "https://github.com/threefoldfoundation/data_partners/tree/master/partners",
    "weblibs": "https://github.com/threefoldtech/jumpscale_weblibs",
}


class Package(j.baseclasses.threebot_package):
    def _init(self, **kwargs):
        self.branch = kwargs["package"].branch or "development"

        self.auto_update_greetlet = None
        # disable auto updates in production
        self.disable_auto_update = self.branch == "master"

    def clone_repos(self, pull=False):
        # clone website
        self._log_debug("Pulling freeflownation.org...")
        yield j.clients.git.getContentPathFromURLorPath(FREEFLOW_ORG, branch=self.branch, pull=pull)

        # all the rest is from master
        for name, url in REPOS.items():
            self._log_debug(f"Pulling {name}")
            yield j.clients.git.getContentPathFromURLorPath(url, pull=pull)

    def auto_pull_worker(self):
        while True:
            try:
                paths = self.clone_repos(pull=True)
                website_path = next(paths)
                self._log_debug("Building freeflownation.org app...")
                j.sal.process.execute(f"cd {website_path} && npm install && npm run build")

                for path in paths:
                    self._log_debug(f"Successfully pulled to {path}")
            except j.exceptions.Base as e:
                j.errorhandler.exception_handle(e, die=False)

            gevent.sleep(200)

    def prepare(self):
        """
        called when the 3bot starts
        :return:
        """

        server = self.openresty
        server.install()
        server.configure()

        website = server.get_from_port(80)
        website.ssl = False
        locations = website.locations.get("freeflownation")

        website_path, team_path, community_path, weblibs_path = self.clone_repos()

        website_location = locations.locations_static.new()
        website_location.name = "freeflownation"
        website_location.path_url = "/"
        website_location.path_location = website_path

        data_team_location = locations.locations_static.new()
        data_team_location.name = "team"
        data_team_location.path_url = "/team_data"
        data_team_location.path_location = team_path

        data_community_location = locations.locations_static.new()
        data_community_location.name = "partners"
        data_community_location.path_url = "/partners_data"
        data_community_location.path_location = community_path

        # need to serve weblibs from /static
        weblibs_location = locations.locations_static.new()
        weblibs_location.name = "weblibs"
        weblibs_location.path_url = "/jumpscaleX_weblibs"
        weblibs_location.path_location = weblibs_path

        rack = j.servers.rack.get()
        app = j.servers.gedishttp.get_app()
        rack.bottle_server_add(name="gedishttp", port=9201, app=app)

        proxy_location = locations.locations_proxy.new()
        proxy_location.name = "gedishttp"
        proxy_location.path_url = "/actors"
        proxy_location.ipaddr_dest = "0.0.0.0"
        proxy_location.port_dest = 9201
        proxy_location.scheme = "http"

        locations.configure()
        website.configure()

    def start(self):
        """
        called when the 3bot starts
        :return:
        """
        if not self.disable_auto_update:
            self.auto_update_greetlet = gevent.spawn(self.auto_pull_worker)

    def stop(self):
        """
        called when the 3bot stops
        :return:
        """
        if self.auto_update_greetlet:
            self.auto_update_greetlet.kill()

    def uninstall(self):
        """
        called when the package is no longer needed and will be removed from the threebot
        :return:
        """
        pass
