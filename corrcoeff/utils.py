import numpy as np

def get_noise(setup):
    lmin, lmax = setup["lmin"], setup["lmax"]
    fsky = setup["fsky"]
    sensitivity_mode = setup["sensitivity_mode"]
    from corrcoeff import V3calc as V3
    ell, N_ell_T_LA, N_ell_P_LA, Map_white_noise_levels \
        = V3.Simons_Observatory_V3_LA_noise(sensitivity_mode, fsky, lmin, lmax, delta_ell=1, apply_beam_correction=True)
    # Keep only relevant rows
    idx = np.intersect1d(setup["freq"], setup["freq_all"], return_indices=True)[-1]
    return N_ell_T_LA[idx], N_ell_P_LA[idx]

def get_theory_cls(setup, lmax, ell_factor=False):
    # Get simulation parameters
    simu = setup["simulation"]
    cosmo = simu["cosmo. parameters"]
    # CAMB use As
    if "logA" in cosmo:
        cosmo["As"] = 1e-10*np.exp(cosmo["logA"])
        del cosmo["logA"]

    # Get cobaya setup
    from copy import deepcopy
    info = deepcopy(setup["cobaya"])
    info["params"] = cosmo
    # Fake likelihood so far
    info["likelihood"] = {"one": None}
    from cobaya.model import get_model
    model = get_model(info)

    model.likelihood.theory.needs(Cl={"tt": lmax, "ee": lmax, "te": lmax})
    model.logposterior({}) # parameters are fixed
    Cls = model.likelihood.theory.get_cl(ell_factor=ell_factor)
    return Cls

def fisher(setup, covmat_params):
    experiment = setup["experiment"]
    lmin, lmax = experiment["lmin"], experiment["lmax"]
    study = experiment["study"]

    from copy import deepcopy

    params = covmat_params
    covmat = setup.get("simulation").get("covmat")
    epsilon = 0.01
    deriv = {}
    for p in params:
        setup_mod = deepcopy(setup)
        parname = p if p != "logA" else "As"
        value = setup["simulation"]["cosmo. parameters"][parname]
        setup_mod["simulation"]["cosmo. parameters"][parname] = (1-epsilon)*value
        Cl_minus = get_theory_cls(setup_mod, lmax)
        setup_mod["simulation"]["cosmo. parameters"][parname] = (1+epsilon)*value
        Cl_plus = get_theory_cls(setup_mod, lmax)
        if study == "R":
            plus = Cl_plus["te"]/np.sqrt(Cl_plus["tt"]*Cl_plus["ee"])
            minus = Cl_minus["te"]/np.sqrt(Cl_minus["tt"]*Cl_minus["ee"])
        elif study == "TE":
            plus = Cl_plus["te"]
            minus = Cl_minus["te"]
        d = (plus[lmin:lmax]-minus[lmin:lmax])/(2*epsilon*value)
        deriv[p] = d if p != "logA" else d*value

    nparam = len(params)
    fisher = np.zeros((nparam,nparam))
    for count1, p1 in enumerate(params):
        for count2, p2 in enumerate(params):
            fisher[count1,count2] = np.sum(covmat**-1*deriv[p1]*deriv[p2])
    cov = np.linalg.inv(fisher)
    print("eigenvalues = ", np.linalg.eigvals(cov))
    for count, p in enumerate(params):
        if p == "logA":
            value = np.log(1e10*setup_mod["simulation"]["cosmo. parameters"]["As"])
        else:
            value = setup_mod["simulation"]["cosmo. parameters"][p]
        print(p, value, np.sqrt(cov[count,count]))
    return cov
