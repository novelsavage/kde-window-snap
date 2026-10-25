#include <wayland-client.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <linux/input-event-codes.h>
#include "fake-input.h"
static struct org_kde_kwin_fake_input *input;
static void global(void *data, struct wl_registry *r, uint32_t name, const char *iface, uint32_t version) {
 if (!strcmp(iface,"org_kde_kwin_fake_input")) input=wl_registry_bind(r,name,&org_kde_kwin_fake_input_interface,4);
}
static void removed(void *data, struct wl_registry *r, uint32_t name) {}
static const struct wl_registry_listener listener={global,removed};
int main(int argc,char **argv) {
 const char *socket=getenv("WAYLAND_DISPLAY");
 if (!socket || strcmp(socket,"snap-test") || argc!=5) {fputs("Only isolated snap-test socket accepted. Usage: drag x1 y1 x2 y2\n",stderr);return 2;}
 struct wl_display *d=wl_display_connect(NULL);if(!d)return 3;
 struct wl_registry *r=wl_display_get_registry(d);wl_registry_add_listener(r,&listener,NULL);wl_display_roundtrip(d);
 if(!input){fputs("No fake input protocol\n",stderr);return 4;}
 org_kde_kwin_fake_input_authenticate(input,"kde-window-snap-test","isolated virtual compositor boundary drag");
 double x=atof(argv[1]), y=atof(argv[2]), tx=atof(argv[3]),ty=atof(argv[4]);
 org_kde_kwin_fake_input_pointer_motion_absolute(input,wl_fixed_from_double(x),wl_fixed_from_double(y));
 wl_display_roundtrip(d);usleep(100000);
 org_kde_kwin_fake_input_button(input,BTN_LEFT,1);wl_display_roundtrip(d);
 for(int i=1;i<=20;i++){org_kde_kwin_fake_input_pointer_motion_absolute(input,wl_fixed_from_double(x+(tx-x)*i/20),wl_fixed_from_double(y+(ty-y)*i/20));wl_display_flush(d);usleep(25000);}
 org_kde_kwin_fake_input_button(input,BTN_LEFT,0);wl_display_roundtrip(d);wl_display_disconnect(d);return 0;
}
