import numpy as np
from torch.autograd import Variable
import torch as torch
from torch import Tensor
import copy
from torch.autograd.gradcheck import zero_gradients
from torch.nn import Module
from numpy import ndarray


def deepfool(image: Tensor, net: Module, penalty:ndarray, ispenalty:bool,num_classes: int = 10, overshoot: float = 0.02, max_iter: int = 50) -> (
        ndarray,
        int,
        int,
        Tensor
):
    """
       :param image: Image of size HxWx3
       :param net: network (input: images, output: values of activation **BEFORE** softmax).
       :param num_classes: num_classes (limits the number of classes to test against, by default = 10)
       :param overshoot: used as a termination criterion to prevent vanishing updates (default = 0.02).
       :param max_iter: maximum number of iterations for deepfool (default = 50)
       :return: minimal perturbation that fools the classifier, number of iterations that it required,
        new estimated_label and perturbed image
    """
    is_cuda = torch.cuda.is_available()
    if is_cuda:

        image = image.cuda()
        net = net.cuda()
    else:
        pass

    f_image = net.forward(Variable(image.unsqueeze(0), requires_grad=True)).data.cpu().numpy().flatten()
    I = (np.array(f_image)).flatten().argsort()[::-1]
    # top-k
    I = I[0:num_classes]
    label = I[0]

    input_shape = image.cpu().numpy().shape
    pert_image = copy.deepcopy(image)  # for permutated variable
    w = np.zeros(input_shape)
    r_tot = np.zeros(input_shape)

    loop_i = 0

    x = Variable(pert_image[None, :], requires_grad=True)  # x = Variable(pert_img.unsqueeze(0), require_grad=True)
    fs = net.forward(x)
    fs_list = [fs[0, I[k]] for k in range(num_classes)]  # arrange result in original argsort list.
    k_i = label  # for permuted label

    while k_i == label and loop_i < max_iter:

        pert = np.inf
        fs[0, I[0]].backward(retain_graph=True)
        grad_orig = x.grad.data.cpu().numpy().copy()  # gradience of J(F(x, i)) where i is the top label of original image. top gradience

        for k in range(1, num_classes):
            zero_gradients(x)

            fs[0, I[k]].backward(retain_graph=True)
            cur_grad = x.grad.data.cpu().numpy().copy()  # get the label i gradience in a top to bottom manner.

            # set new w_k and new f_k
            w_k = cur_grad - grad_orig
            f_k = (fs[0, I[k]] - fs[0, I[0]]).data.cpu().numpy()  # probability difference

            pert_k = abs(f_k) / np.linalg.norm(w_k.flatten())
            pert_k_pen = pert_k*penalty[label][k_i]
            # determine which w_k to use
            if pert_k_pen < pert:
                pert = pert_k
                w = w_k

        # compute r_i and r_tot
        # Added 1e-4 for numerical stability
        r_i = (pert + 1e-4) * w / np.linalg.norm(w)
        r_tot = np.float32(r_tot + r_i)

        if is_cuda:
            pert_image = image + (1 + overshoot) * torch.from_numpy(r_tot).cuda()
        else:
            pert_image = image + (1 + overshoot) * torch.from_numpy(r_tot)

        x = Variable(pert_image, requires_grad=True)
        fs = net.forward(x)
        k_i = np.argmax(fs.data.cpu().numpy().flatten())

        loop_i += 1

    r_tot = (1 + overshoot) * r_tot
    if(ispenalty):
        penalty[label][k_i] *= 1.1

    return r_tot, loop_i, label, k_i, pert_image
